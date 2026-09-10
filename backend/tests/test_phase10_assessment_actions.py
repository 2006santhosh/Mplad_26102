import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth_utils import get_current_user
from app.database import get_db
from app.main import app
from app.models import (
    Base,
    ComplianceAssessment,
    DataSource,
    MP,
    PredictiveCompletionAssessment,
    Project,
    RiskAssessment,
    RiskHistory,
)


engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)
client = TestClient(app)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def make_user(role: str):
    return {"sub": "phase10_test", "role": role}


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    source = DataSource(id=1, source_name="Phase 10 Test Official", source_type="OFFICIAL")
    mp = MP(id=1, data_source_id=1, name="Phase 10 Test MP", state="Test State")
    project = Project(
        id=1,
        mp_id=1,
        data_source_id=1,
        category="Road",
        status="ONGOING",
        sanctioned_amount=100000,
        work_stage="Sanction",
    )
    db.add_all([source, mp, project])
    db.commit()
    db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: make_user("Admin")
    yield
    app.dependency_overrides.clear()


def test_post_risk_assessment_persists_and_get_compatibility_remains():
    response = client.post("/api/projects/1/risk")
    assert response.status_code == 200, response.text
    assert response.json()["assessment_status"]

    db = TestingSessionLocal()
    assert db.query(RiskAssessment).filter(RiskAssessment.project_id == 1).count() == 1
    assert db.query(RiskHistory).filter(RiskHistory.project_id == 1).count() == 1
    db.close()

    legacy_response = client.get("/api/projects/1/risk")
    assert legacy_response.status_code == 200, legacy_response.text


def test_get_risk_without_assessment_is_read_only_and_unassessed():
    response = client.get("/api/projects/1/risk")
    assert response.status_code == 200
    assert response.json()["assessment_status"] == "NOT_ASSESSABLE"
    assert response.json()["assessment_coverage"] is None

    db = TestingSessionLocal()
    assert db.query(RiskAssessment).count() == 0
    assert db.query(RiskHistory).count() == 0
    db.close()


def test_get_risk_with_existing_assessment_does_not_add_snapshot():
    client.post("/api/projects/1/risk")
    db = TestingSessionLocal()
    before = (db.query(RiskAssessment).count(), db.query(RiskHistory).count())
    db.close()

    response = client.get("/api/projects/1/risk")
    assert response.status_code == 200

    db = TestingSessionLocal()
    assert (db.query(RiskAssessment).count(), db.query(RiskHistory).count()) == before
    db.close()


def test_get_compliance_without_assessment_is_read_only_and_unassessed():
    response = client.get("/api/projects/1/compliance/")
    assert response.status_code == 200
    assert response.json()["overall_status"] == "NOT_ASSESSABLE"
    assert response.json()["coverage_percentage"] is None

    db = TestingSessionLocal()
    assert db.query(ComplianceAssessment).count() == 0
    db.close()


def test_review_priority_is_consistent_across_consumers():
    project_response = client.get("/api/projects").json()[0]
    dashboard_response = client.get("/api/dashboard/stats").json()
    decision_response = client.get("/api/projects/1/decision-support").json()

    assert project_response["review_priority_level"] == "MEDIUM"
    assert dashboard_response["review_priority_medium"] == 1
    assert decision_response["review_priority"]["level"] == "MEDIUM"


def test_include_demo_preserves_synthetic_provenance():
    db = TestingSessionLocal()
    synthetic_source = DataSource(id=2, source_name="Phase 10 Synthetic", source_type="SYNTHETIC")
    synthetic_mp = MP(id=2, data_source_id=2, name="Synthetic MP", state="Synthetic State")
    synthetic_project = Project(
        id=2,
        mp_id=2,
        data_source_id=2,
        category="Demo Road",
        sanctioned_amount=0,
        work_stage="Demo Stage",
    )
    db.add_all([synthetic_source, synthetic_mp, synthetic_project])
    db.commit()
    db.close()

    response = client.get("/api/projects?include_demo=true")
    assert response.status_code == 200
    synthetic = next(item for item in response.json() if item["id"] == 2)
    assert synthetic["provenance"]["sanctioned_amount"] == "SYNTHETIC"
    assert synthetic["provenance"]["work_stage"] == "SYNTHETIC"


def test_predictive_post_requires_reviewer_role():
    app.dependency_overrides[get_current_user] = lambda: make_user("Viewer")
    response = client.post("/api/projects/1/predictive-completion/assess")
    assert response.status_code == 403


def test_predictive_post_persists_for_reviewer_role():
    response = client.post("/api/projects/1/predictive-completion/assess")
    assert response.status_code == 200, response.text

    db = TestingSessionLocal()
    assert db.query(PredictiveCompletionAssessment).filter(
        PredictiveCompletionAssessment.project_id == 1
    ).count() == 1
    db.close()
