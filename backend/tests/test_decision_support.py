import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import get_db
from app.auth_utils import get_current_user
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
from app.models import DataSource, Base, Project, ProjectProgress, ProjectFinancials, RiskAssessment, ComplianceAssessment, EarlyWarning, PredictiveCompletionAssessment, RiskHistory
import datetime

engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    if not db.query(DataSource).filter(DataSource.id == 1).first():
        db.add(DataSource(id=1, source_name="Official Data", source_type="OFFICIAL"))
        db.commit()
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
    
    # Fully populated project 1 — normal numeric coverage (90.0)
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

    # Project 3 — RiskAssessment exists but assessment_coverage_pct is NULL (the regression scenario)
    p3 = Project(id=3, mp_id=1, data_source_id=1, sanctioned_amount=500000, status="ONGOING")
    db.add(p3)
    db.add(RiskAssessment(project_id=3, score=50, overall_risk_level="MEDIUM", assessment_coverage_pct=None, created_at=now))

    # Project 4 — RiskAssessment exists with coverage = 0 (zero is a real numeric value, not None)
    p4 = Project(id=4, mp_id=1, data_source_id=1, sanctioned_amount=500000, status="ONGOING")
    db.add(p4)
    db.add(RiskAssessment(project_id=4, score=40, overall_risk_level="LOW", assessment_coverage_pct=0.0, created_at=now))

    # Project 5 — MEDIUM risk, no history (tests review priority preservation)
    p5 = Project(id=5, mp_id=1, data_source_id=1, sanctioned_amount=500000, status="ONGOING")
    db.add(p5)
    db.add(RiskAssessment(project_id=5, score=55, overall_risk_level="MEDIUM", assessment_coverage_pct=75.0, created_at=now))

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

# ---------------------------------------------------------------------------
# Regression tests — NULL / zero coverage bug (Phase 9 fix)
# ---------------------------------------------------------------------------

def test_coverage_numeric_unchanged():
    """TEST 1: Normal numeric coverage (90.0) — existing behavior preserved."""
    response = client.get("/api/projects/1/decision-support")
    assert response.status_code == 200
    data = response.json()
    # coverage is 90.0 — well above 30, so "Low evidence coverage" signal must NOT appear
    signals = data["review_priority"]["contributing_signals"]
    assert "Low evidence coverage" not in signals
    # evidence_coverage must be the actual numeric value
    assert data["review_priority"]["evidence_coverage"] == 90.0

def test_coverage_none_no_500():
    """TEST 2: coverage = None — must return HTTP 200, no TypeError, coverage stays None."""
    response = client.get("/api/projects/3/decision-support")
    assert response.status_code == 200
    data = response.json()
    # coverage must remain None (unavailable), not coerced to 0
    assert data["review_priority"]["evidence_coverage"] is None
    # "Low evidence coverage" must NOT be added when coverage is None
    # (None != insufficient-numeric; we simply cannot assess coverage)
    signals = data["review_priority"]["contributing_signals"]
    assert "Low evidence coverage" not in signals

def test_coverage_zero_is_numeric():
    """TEST 3: coverage = 0 — treated as real numeric 0, not as None."""
    response = client.get("/api/projects/4/decision-support")
    assert response.status_code == 200
    data = response.json()
    # 0 < 30 so "Low evidence coverage" MUST appear
    signals = data["review_priority"]["contributing_signals"]
    assert "Low evidence coverage" in signals
    # evidence_coverage must be exactly 0, not None
    assert data["review_priority"]["evidence_coverage"] == 0.0

def test_review_priority_preserved_medium_risk():
    """TEST 5: Review Priority — MEDIUM risk with sufficient coverage stays MEDIUM."""
    response = client.get("/api/projects/5/decision-support")
    assert response.status_code == 200
    data = response.json()
    # MEDIUM risk, no warnings, no compliance issues, coverage 75% (above 30)
    assert data["review_priority"]["level"] == "MEDIUM"
    assert "Low evidence coverage" not in data["review_priority"]["contributing_signals"]

def teardown_module():
    app.dependency_overrides.clear()

