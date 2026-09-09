import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import get_db
from app.auth_utils import get_current_user
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
from app.models import Base, Project, ProjectProgress, ProjectFinancials, RiskAssessment, ComplianceAssessment, PredictiveCompletionAssessment
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

    # Helper to add project
    def add_project(id_val, **kwargs):
        db.add(Project(id=id_val, mp_id=1, data_source_id=1, **kwargs))

    # 1. Fully assessable project with HIGH risk
    add_project(1, sanctioned_amount=1000000, status="ONGOING")
    db.add(ProjectProgress(project_id=1, percentage=30, reported_at=now - datetime.timedelta(days=200)))
    db.add(ProjectFinancials(project_id=1, expenditure=850000, updated_at=now))
    db.add(RiskAssessment(project_id=1, score=40, overall_risk_level="MEDIUM", created_at=now - datetime.timedelta(days=30)))
    db.add(RiskAssessment(project_id=1, score=70, overall_risk_level="HIGH", created_at=now))
    db.add(ComplianceAssessment(project_id=1, overall_status="FAIL", coverage_percentage=100.0, engine_version="7.0.0", assessed_at=now))

    # 2. Missing essential data -> NOT_ASSESSABLE
    add_project(2, sanctioned_amount=1000000, status="ONGOING")

    # 3. Stable trajectory -> LOW risk
    add_project(3, sanctioned_amount=1000000, status="ONGOING")
    db.add(ProjectProgress(project_id=3, percentage=50, reported_at=now - datetime.timedelta(days=10)))
    db.add(ProjectFinancials(project_id=3, expenditure=400000, updated_at=now))
    db.add(RiskAssessment(project_id=3, score=20, overall_risk_level="LOW", created_at=now - datetime.timedelta(days=30)))
    db.add(RiskAssessment(project_id=3, score=20, overall_risk_level="LOW", created_at=now))
    db.add(ComplianceAssessment(project_id=3, overall_status="PASS", coverage_percentage=100.0, engine_version="7.0.0", assessed_at=now))

    # 4. Missing compliance
    add_project(4, sanctioned_amount=1000000, status="ONGOING")
    db.add(ProjectProgress(project_id=4, percentage=50, reported_at=now - datetime.timedelta(days=10)))
    db.add(ProjectFinancials(project_id=4, expenditure=400000, updated_at=now))
    db.add(RiskAssessment(project_id=4, score=20, overall_risk_level="LOW", created_at=now - datetime.timedelta(days=30)))
    db.add(RiskAssessment(project_id=4, score=20, overall_risk_level="LOW", created_at=now))

    # 5. Compliance REVIEW
    add_project(5, sanctioned_amount=1000000, status="ONGOING")
    db.add(ProjectProgress(project_id=5, percentage=50, reported_at=now - datetime.timedelta(days=10)))
    db.add(ProjectFinancials(project_id=5, expenditure=400000, updated_at=now))
    db.add(RiskAssessment(project_id=5, score=20, overall_risk_level="LOW", created_at=now - datetime.timedelta(days=30)))
    db.add(RiskAssessment(project_id=5, score=20, overall_risk_level="LOW", created_at=now))
    db.add(ComplianceAssessment(project_id=5, overall_status="REVIEW", coverage_percentage=100.0, engine_version="7.0.0", assessed_at=now))

    # 8. Decreasing risk trajectory
    add_project(6, sanctioned_amount=1000000, status="ONGOING")
    db.add(ProjectProgress(project_id=6, percentage=50, reported_at=now - datetime.timedelta(days=10)))
    db.add(ProjectFinancials(project_id=6, expenditure=400000, updated_at=now))
    db.add(RiskAssessment(project_id=6, score=80, overall_risk_level="CRITICAL", created_at=now - datetime.timedelta(days=30)))
    db.add(RiskAssessment(project_id=6, score=20, overall_risk_level="LOW", created_at=now))
    db.add(ComplianceAssessment(project_id=6, overall_status="PASS", coverage_percentage=100.0, engine_version="7.0.0", assessed_at=now))
    
    # 12. NULL risk values handling
    add_project(7, sanctioned_amount=1000000, status="ONGOING")
    db.add(ProjectProgress(project_id=7, percentage=50, reported_at=now - datetime.timedelta(days=10)))
    db.add(RiskAssessment(project_id=7, score=None, overall_risk_level="LOW", created_at=now - datetime.timedelta(days=30)))
    db.add(RiskAssessment(project_id=7, score=None, overall_risk_level="LOW", created_at=now))
    
    # 13. Missing financial data
    add_project(8, status="ONGOING") # no sanctioned amount
    db.add(ProjectProgress(project_id=8, percentage=50, reported_at=now - datetime.timedelta(days=10)))
    db.add(RiskAssessment(project_id=8, score=20, overall_risk_level="LOW", created_at=now - datetime.timedelta(days=30)))
    db.add(RiskAssessment(project_id=8, score=20, overall_risk_level="LOW", created_at=now))

    db.commit()
    db.close()

def test_1_fully_assessable_project():
    response = client.post("/api/projects/1/predictive-completion/assess")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ASSESSABLE"
    assert data["risk_level"] in ["HIGH", "CRITICAL"]

def test_2_not_assessable():
    response = client.post("/api/projects/2/predictive-completion/assess")
    data = response.json()
    assert data["status"] == "NOT_ASSESSABLE"
    assert data["risk_level"] is None

def test_4_missing_compliance():
    # project 4 has missing compliance
    response = client.post("/api/projects/4/predictive-completion/assess")
    data = response.json()
    assert data["status"] == "ASSESSABLE"
    assert "Compliance assessment unavailable" in data["missing_data"]

def test_5_missing_compliance_does_not_increase_risk():
    # project 4 has missing compliance, project 3 has PASS compliance. Risk level should be same (LOW)
    r3 = client.post("/api/projects/3/predictive-completion/assess").json()
    r4 = client.post("/api/projects/4/predictive-completion/assess").json()
    assert r3["risk_level"] == r4["risk_level"]
    # however confidence or coverage might differ
    assert r4["coverage_pct"] < r3["coverage_pct"]

def test_6_compliance_review():
    r = client.post("/api/projects/5/predictive-completion/assess").json()
    assert any("REVIEW" in driver for driver in r["drivers"])

def test_7_compliance_fail():
    r = client.post("/api/projects/1/predictive-completion/assess").json()
    assert any("FAILED" in driver for driver in r["drivers"])

def test_8_increasing_risk_trajectory():
    r = client.post("/api/projects/1/predictive-completion/assess").json()
    assert any("increasing" in driver for driver in r["drivers"])

def test_9_stable_trajectory():
    r = client.post("/api/projects/3/predictive-completion/assess").json()
    assert not any("increasing" in driver for driver in r["drivers"])

def test_10_decreasing_trajectory():
    r = client.post("/api/projects/6/predictive-completion/assess").json()
    assert not any("increasing" in driver for driver in r["drivers"])
    assert r["risk_level"] == "LOW" # Decreased from Critical to Low

def test_11_insufficient_risk_history():
    r = client.post("/api/projects/7/predictive-completion/assess").json()
    assert "Insufficient historical risk assessments" in r["missing_data"]

def test_12_null_risk_values():
    r = client.post("/api/projects/7/predictive-completion/assess").json()
    assert "Insufficient historical risk assessments" in r["missing_data"]

def test_13_missing_financial_data():
    r = client.post("/api/projects/8/predictive-completion/assess").json()
    assert r["status"] == "ASSESSABLE"
    assert "expenditure_ratio" not in r["evidence"]

def test_14_financial_progress_mismatch():
    r = client.post("/api/projects/1/predictive-completion/assess").json()
    assert any("High financial implementation" in d for d in r["drivers"])

def test_17_analytical_progress_proxy_wording():
    r = client.post("/api/projects/1/predictive-completion/assess").json()
    assert "analytical_progress_proxy" in r["evidence"]
    assert not any("official physical progress" in d.lower() for d in r["drivers"])
    
    r2 = client.post("/api/projects/2/predictive-completion/assess").json()
    assert "Analytical Progress Proxy unavailable" in r2["missing_data"]

def test_18_get_is_readonly():
    # count records
    db = TestingSessionLocal()
    count_before = db.query(PredictiveCompletionAssessment).count()
    db.close()

    r = client.get("/api/projects/1/predictive-completion")
    
    db = TestingSessionLocal()
    count_after = db.query(PredictiveCompletionAssessment).count()
    db.close()
    assert count_before == count_after

def test_19_post_persists():
    r = client.post("/api/projects/1/predictive-completion/assess")
    db = TestingSessionLocal()
    count = db.query(PredictiveCompletionAssessment).filter_by(project_id=1).count()
    db.close()
    assert count > 0

def test_20_historical_persistence():
    db = TestingSessionLocal()
    initial_count = db.query(PredictiveCompletionAssessment).filter_by(project_id=3).count()
    db.close()

    r1 = client.post("/api/projects/3/predictive-completion/assess")
    r2 = client.post("/api/projects/3/predictive-completion/assess")
    
    db = TestingSessionLocal()
    final_count = db.query(PredictiveCompletionAssessment).filter_by(project_id=3).count()
    db.close()
    assert final_count == initial_count + 2

def test_21_provenance():
    r = client.post("/api/projects/3/predictive-completion/assess").json()
    assert r["provenance"] == "AI ASSESSMENT"

def test_22_engine_version():
    r = client.post("/api/projects/3/predictive-completion/assess").json()
    assert r["engine_version"] == "7.0.0"

def test_23_api_response_schema():
    r = client.post("/api/projects/3/predictive-completion/assess").json()
    assert "status" in r
    assert "risk_level" in r
    assert "confidence" in r
    assert "coverage_pct" in r
    assert "drivers" in r

def teardown_module():
    app.dependency_overrides.clear()
