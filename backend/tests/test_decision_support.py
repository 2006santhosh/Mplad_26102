import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import get_db
from app.auth_utils import get_current_user
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
from app.models import Base, Project, ProjectProgress, ProjectFinancials, RiskAssessment, ComplianceAssessment, EarlyWarning, PredictiveCompletionAssessment, RiskHistory
import datetime

engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

client = TestClient(app)

def setup_module():
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: {'sub': 'test', 'role': 'Admin'}
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    
    now = datetime.datetime.now(datetime.UTC)
    
    # Fully populated project 1
    p1 = Project(id=1, mp_id=1, data_source_id=1, sanctioned_amount=1000000, status="ONGOING", latitude=10.0, longitude=20.0, planned_start=now.date())
    db.add(p1)
    db.add(ProjectProgress(project_id=1, percentage=50, reported_at=now))
    db.add(ProjectFinancials(project_id=1, expenditure=500000, updated_at=now))
    db.add(RiskAssessment(project_id=1, score=80, overall_risk_level="HIGH", assessment_coverage_pct=90.0, created_at=now))
    db.add(ComplianceAssessment(project_id=1, overall_status="FAIL", coverage_percentage=100.0, fail_count=2, assessed_at=now))
    db.add(EarlyWarning(project_id=1, warning_type="FINANCIAL", warning_level="CRITICAL", status="OPEN", title="Cost Overrun", explanation="Exceeded limit", trigger_signature="cost_1", engine_version="v1"))
    db.add(PredictiveCompletionAssessment(project_id=1, status="ASSESSABLE", risk_level="HIGH", risk_score=85, confidence="HIGH", created_at=now))
    
    db.add(RiskHistory(project_id=1, risk_score=30, risk_level="LOW", recorded_at=now - datetime.timedelta(days=60)))
    db.add(RiskHistory(project_id=1, risk_score=80, risk_level="HIGH", recorded_at=now))

    # Empty project 2
    p2 = Project(id=2, mp_id=1, data_source_id=1, sanctioned_amount=1000000, status="ONGOING")
    db.add(p2)

    db.commit()
    db.close()

def test_unified_decision_support_response():
    response = client.get("/api/projects/1/decision-support")
    assert response.status_code == 200
    data = response.json()
    assert data["project_id"] == 1
    assert data["overall_risk"]["level"] == "HIGH"
    assert data["compliance"]["status"] == "FAIL"
    assert len(data["early_warnings"]) == 1
    assert data["completion_risk"]["level"] == "HIGH"

def test_risk_trend_aggregation():
    data = client.get("/api/projects/1/decision-support").json()
    assert data["risk_trend"]["trend"] == "INCREASING"

def test_review_priority_logic():
    data = client.get("/api/projects/1/decision-support").json()
    assert data["review_priority"]["level"] == "CRITICAL" # because open critical warning
    assert len(data["review_priority"]["contributing_signals"]) > 0

def test_missing_data_visibility():
    data = client.get("/api/projects/2/decision-support").json()
    assert data["data_quality"]["gps_coverage"] == "UNAVAILABLE"
    assert data["data_quality"]["analytical_progress_coverage"] == "UNAVAILABLE"
    assert data["review_priority"]["level"] == "MEDIUM" # elevated due to low coverage

def test_timeline_contains_real_events():
    data = client.get("/api/projects/1/decision-support").json()
    timeline = data["timeline"]
    assert len(timeline) > 0
    event_types = [e["event_type"] for e in timeline]
    assert "Sanction recorded" in event_types
    assert "Progress Update" in event_types
    assert "Risk Assessment" in event_types

def teardown_module():
    app.dependency_overrides.clear()
