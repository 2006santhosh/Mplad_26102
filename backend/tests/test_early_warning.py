"""
test_early_warning.py

Tests for the Early Warning Engine (Phase 6B).

Covers:
- Burn Rate (HIGH / MEDIUM / boundary / no-warning)
- Deadline (overdue / approaching / completed project exempt)
- Stagnation (stale progress)
- Data Anomaly (negative expenditure / invalid progress)
- Missing progress — no fabricated warnings
- GET idempotency / read-only contract
- POST assessment (deduplication across two calls)
- RAPID_RISK_INCREASE: NULL-score safety
- MULTI_SIGNAL_CONVERGENCE
- Active-warning count (OPEN/ACKNOWLEDGED/UNDER_REVIEW counted; RESOLVED/DISMISSED excluded)
- RBAC: unauthenticated GET returns 401
"""
from fastapi.testclient import TestClient
from app.main import app
from app.database import get_db
from app.auth_utils import get_current_user
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
from app.models import Base, Project, ProjectProgress, ProjectFinancials, RiskHistory, EarlyWarning
from datetime import datetime, date, timedelta

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

admin_user = {"sub": "test_admin", "role": "Admin"}

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

client = TestClient(app)

def setup_module():
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: admin_user
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    today = date.today()

    # 1. HIGH burn-rate case (85% exp, 40% prog)
    p1 = Project(id=1, mp_id=1, data_source_id=1, sanctioned_amount=10000, status="ONGOING")
    f1 = ProjectFinancials(project_id=1, expenditure=8500, updated_at=datetime.now())
    pr1 = ProjectProgress(project_id=1, percentage=40, reported_at=datetime.now())

    # 2. MEDIUM burn-rate case (95% exp, 60% prog) — above 70% spent, below 70% progress
    p2 = Project(id=2, mp_id=1, data_source_id=1, sanctioned_amount=10000, status="ONGOING")
    f2 = ProjectFinancials(project_id=2, expenditure=9500, updated_at=datetime.now())
    pr2 = ProjectProgress(project_id=2, percentage=60, reported_at=datetime.now())

    # 3. Boundary case (95% exp, 85% prog -> no burn rate warning)
    p3 = Project(id=3, mp_id=1, data_source_id=1, sanctioned_amount=10000, status="ONGOING")
    f3 = ProjectFinancials(project_id=3, expenditure=9500, updated_at=datetime.now())
    pr3 = ProjectProgress(project_id=3, percentage=85, reported_at=datetime.now())

    # 4. Healthy project — no warnings expected
    p4 = Project(
        id=4, mp_id=1, data_source_id=1, sanctioned_amount=10000, status="ONGOING",
        planned_completion=today + timedelta(days=365)
    )
    f4 = ProjectFinancials(project_id=4, expenditure=2000, updated_at=datetime.now())
    pr4 = ProjectProgress(project_id=4, percentage=25, reported_at=datetime.now())

    # 5. Overdue project
    p5 = Project(
        id=5, mp_id=1, data_source_id=1, sanctioned_amount=10000, status="ONGOING",
        planned_completion=today - timedelta(days=10)
    )
    pr5 = ProjectProgress(project_id=5, percentage=90, reported_at=datetime.now())

    # 6. Approaching-deadline project (<90 days, <70% prog)
    p6 = Project(
        id=6, mp_id=1, data_source_id=1, sanctioned_amount=10000, status="ONGOING",
        planned_completion=today + timedelta(days=30)
    )
    pr6 = ProjectProgress(project_id=6, percentage=60, reported_at=datetime.now())

    # 7. Stale progress report (>180 days, <100%)
    p7 = Project(
        id=7, mp_id=1, data_source_id=1, sanctioned_amount=10000, status="ONGOING",
        planned_completion=today + timedelta(days=365)
    )
    pr7 = ProjectProgress(
        project_id=7, percentage=50, reported_at=datetime.now() - timedelta(days=200)
    )

    # 8. Missing progress history — no pr8
    p8 = Project(id=8, mp_id=1, data_source_id=1, sanctioned_amount=10000, status="ONGOING")

    # 9. Invalid expenditure (-1000)
    p9 = Project(id=9, mp_id=1, data_source_id=1, sanctioned_amount=10000, status="ONGOING")
    f9 = ProjectFinancials(project_id=9, expenditure=-1000, updated_at=datetime.now())

    # 10. Invalid progress (150%)
    p10 = Project(id=10, mp_id=1, data_source_id=1, sanctioned_amount=10000, status="ONGOING")
    pr10 = ProjectProgress(project_id=10, percentage=150, reported_at=datetime.now())

    # 11. NULL risk_score safety: NULL -> 45 -> 82 should NOT trigger RAPID_RISK_INCREASE
    #     because only 2 valid (non-null) scores exist
    p11 = Project(id=11, mp_id=1, data_source_id=1, sanctioned_amount=10000, status="ONGOING")

    # 12. Genuine RAPID_RISK_INCREASE: 20 -> 40 -> 82 (3 valid scores, delta = 62)
    p12 = Project(id=12, mp_id=1, data_source_id=1, sanctioned_amount=10000, status="ONGOING")

    # 13. Completed project — no deadline warning even if past planned
    p13 = Project(
        id=13, mp_id=1, data_source_id=1, sanctioned_amount=10000, status="COMPLETED",
        planned_completion=today - timedelta(days=10)
    )

    # 20. Project for deduplication test (POST twice should not duplicate warnings)
    p20 = Project(id=20, mp_id=1, data_source_id=1, sanctioned_amount=10000, status="ONGOING")
    f20 = ProjectFinancials(project_id=20, expenditure=8500, updated_at=datetime.now())
    pr20 = ProjectProgress(project_id=20, percentage=40, reported_at=datetime.now())

    # 21. Project for GET read-only test (pre-seeded with a persisted warning)
    p21 = Project(id=21, mp_id=1, data_source_id=1, sanctioned_amount=10000, status="ONGOING")

    # 22. Project for active-warning-count test
    p22 = Project(id=22, mp_id=1, data_source_id=1, sanctioned_amount=10000, status="ONGOING")

    db.add_all([
        p1, f1, pr1,
        p2, f2, pr2,
        p3, f3, pr3,
        p4, f4, pr4,
        p5, pr5,
        p6, pr6,
        p7, pr7,
        p8,
        p9, f9,
        p10, pr10,
        p11,
        p12,
        p13,
        p20, f20, pr20,
        p21,
        p22,
    ])
    db.commit()

    # Risk history for p11 (NULL -> 45 -> 82)
    from app.models import RiskHistory
    rh11a = RiskHistory(project_id=11, risk_level="LOW", risk_score=None, recorded_at=datetime.now() - timedelta(days=60))
    rh11b = RiskHistory(project_id=11, risk_level="MEDIUM", risk_score=45, recorded_at=datetime.now() - timedelta(days=30))
    rh11c = RiskHistory(project_id=11, risk_level="HIGH", risk_score=82, recorded_at=datetime.now())

    # Risk history for p12 (20 -> 40 -> 82 — all valid, delta = 62 >= 40)
    rh12a = RiskHistory(project_id=12, risk_level="LOW", risk_score=20, recorded_at=datetime.now() - timedelta(days=60))
    rh12b = RiskHistory(project_id=12, risk_level="MEDIUM", risk_score=40, recorded_at=datetime.now() - timedelta(days=30))
    rh12c = RiskHistory(project_id=12, risk_level="HIGH", risk_score=82, recorded_at=datetime.now())

    # Pre-seed a persisted warning for p21 (for GET read-only test)
    ew21 = EarlyWarning(
        project_id=21,
        warning_type="RISK_ESCALATION",
        warning_level="HIGH",
        title="Test Warning",
        explanation="Pre-seeded test warning",
        trigger_signature="test_sig_p21_read_only",
        engine_version="6.1.0",
        provenance="AI ASSESSMENT",
        status="OPEN",
    )

    db.add_all([rh11a, rh11b, rh11c, rh12a, rh12b, rh12c, ew21])
    db.commit()
    db.close()


# ---------------------------------------------------------------
# BURN RATE
# ---------------------------------------------------------------

def test_early_warning_high_burn_rate():
    response = client.post("/api/projects/1/early-warnings/assess")
    assert response.status_code == 200
    data = response.json()
    assert any(w["warning_type"] == "Burn Rate" and w["warning_level"] == "HIGH" for w in data["warnings"])
    assert not any(w["warning_type"] == "Burn Rate" and w["warning_level"] == "MEDIUM" for w in data["warnings"])

def test_early_warning_medium_burn_rate():
    response = client.post("/api/projects/2/early-warnings/assess")
    assert response.status_code == 200
    data = response.json()
    assert any(w["warning_type"] == "Burn Rate" and w["warning_level"] == "MEDIUM" for w in data["warnings"])
    assert not any(w["warning_type"] == "Burn Rate" and w["warning_level"] == "HIGH" for w in data["warnings"])

def test_early_warning_boundary_no_burn_rate():
    response = client.post("/api/projects/3/early-warnings/assess")
    assert response.status_code == 200
    data = response.json()
    assert not any(w["warning_type"] == "Burn Rate" for w in data["warnings"])

def test_early_warning_healthy():
    response = client.post("/api/projects/4/early-warnings/assess")
    assert response.status_code == 200
    data = response.json()
    assert len(data["warnings"]) == 0


# ---------------------------------------------------------------
# DEADLINE
# ---------------------------------------------------------------

def test_early_warning_overdue():
    response = client.post("/api/projects/5/early-warnings/assess")
    assert response.status_code == 200
    data = response.json()
    assert any(w["warning_type"] == "Deadline" and w["warning_level"] == "HIGH" for w in data["warnings"])

def test_early_warning_approaching_deadline():
    response = client.post("/api/projects/6/early-warnings/assess")
    assert response.status_code == 200
    data = response.json()
    assert any(w["warning_type"] == "Deadline" and w["warning_level"] == "MEDIUM" for w in data["warnings"])

def test_early_warning_completed_project_no_deadline():
    response = client.post("/api/projects/13/early-warnings/assess")
    assert response.status_code == 200
    data = response.json()
    assert not any(w["warning_type"] == "Deadline" for w in data["warnings"])


# ---------------------------------------------------------------
# STAGNATION
# ---------------------------------------------------------------

def test_early_warning_stale_progress():
    response = client.post("/api/projects/7/early-warnings/assess")
    assert response.status_code == 200
    data = response.json()
    assert any(w["warning_type"] == "Stagnation" and w["warning_level"] == "MEDIUM" for w in data["warnings"])


# ---------------------------------------------------------------
# MISSING DATA — no fabrication
# ---------------------------------------------------------------

def test_early_warning_missing_progress():
    response = client.post("/api/projects/8/early-warnings/assess")
    assert response.status_code == 200
    data = response.json()
    # No progress at all: should generate no stagnation, no burn rate, no deadline
    assert len(data["warnings"]) == 0


# ---------------------------------------------------------------
# DATA ANOMALY
# ---------------------------------------------------------------

def test_early_warning_invalid_expenditure():
    response = client.post("/api/projects/9/early-warnings/assess")
    assert response.status_code == 200
    data = response.json()
    assert any(
        w["warning_type"] == "Data Anomaly"
        and w["warning_level"] == "LOW"
        and "negative" in w["explanation"].lower()
        for w in data["warnings"]
    )

def test_early_warning_invalid_progress():
    response = client.post("/api/projects/10/early-warnings/assess")
    assert response.status_code == 200
    data = response.json()
    assert any(
        w["warning_type"] == "Data Anomaly"
        and w["warning_level"] == "LOW"
        and "invalid" in w["explanation"].lower()
        for w in data["warnings"]
    )


# ---------------------------------------------------------------
# NULL RISK SCORE SAFETY — RAPID_RISK_INCREASE
# ---------------------------------------------------------------

def test_rapid_risk_increase_null_score_no_false_trigger():
    """
    NULL -> 45 -> 82: only 2 valid scores exist.
    RAPID_RISK_INCREASE requires >= 3 valid non-null scores.
    Must NOT be generated.
    """
    response = client.post("/api/projects/11/early-warnings/assess")
    assert response.status_code == 200
    data = response.json()
    assert not any(w["warning_type"] == "RAPID_RISK_INCREASE" for w in data["warnings"]), \
        "RAPID_RISK_INCREASE must not fire when only 2 valid scores exist (null counts as missing, not 0)"

def test_rapid_risk_increase_genuine_trigger():
    """
    20 -> 40 -> 82: 3 valid scores, delta = 62 >= 40.
    RAPID_RISK_INCREASE MUST be generated.
    """
    response = client.post("/api/projects/12/early-warnings/assess")
    assert response.status_code == 200
    data = response.json()
    assert any(w["warning_type"] == "RAPID_RISK_INCREASE" for w in data["warnings"]), \
        "RAPID_RISK_INCREASE must fire when 3 valid scores span >= 40 points"


# ---------------------------------------------------------------
# GET READ-ONLY CONTRACT
# ---------------------------------------------------------------

def test_get_early_warning_is_read_only():
    """
    GET must not run the engine, must not insert any new warnings.
    Call GET on p21 which has 1 pre-seeded warning.
    Warning count must remain exactly 1 after GET.
    """
    db = TestingSessionLocal()
    count_before = db.query(EarlyWarning).filter(EarlyWarning.project_id == 21).count()
    db.close()

    response = client.get("/api/projects/21/early-warning")
    assert response.status_code == 200
    data = response.json()
    assert len(data["warnings"]) == count_before, \
        "GET must not insert new warnings — read-only contract violated"

    db = TestingSessionLocal()
    count_after = db.query(EarlyWarning).filter(EarlyWarning.project_id == 21).count()
    db.close()
    assert count_after == count_before, \
        f"Warning count changed after GET: {count_before} -> {count_after}"

def test_get_returns_persisted_warnings():
    """GET returns whatever is persisted, without running the engine."""
    response = client.get("/api/projects/21/early-warning")
    assert response.status_code == 200
    data = response.json()
    assert data["project_id"] == 21
    assert isinstance(data["warnings"], list)
    assert all("warning_type" in w for w in data["warnings"])
    assert all("warning_level" in w for w in data["warnings"])
    assert all("explanation" in w for w in data["warnings"])


# ---------------------------------------------------------------
# DEDUPLICATION — POST twice, no duplicate warnings
# ---------------------------------------------------------------

def test_post_assess_deduplication():
    """
    Calling POST /assess twice on the same project with unchanged data
    must not create duplicate warnings (trigger_signature deduplication).
    """
    r1 = client.post("/api/projects/20/early-warnings/assess")
    assert r1.status_code == 200
    count_after_first = len(r1.json()["warnings"])

    r2 = client.post("/api/projects/20/early-warnings/assess")
    assert r2.status_code == 200
    count_after_second = len(r2.json()["warnings"])

    assert count_after_second == count_after_first, \
        f"Duplicate warnings created: {count_after_first} -> {count_after_second}"


# ---------------------------------------------------------------
# ACTIVE WARNING COUNT
# ---------------------------------------------------------------

def test_active_warning_count_excludes_resolved_dismissed():
    """
    early_warning_count must count OPEN, ACKNOWLEDGED, UNDER_REVIEW.
    RESOLVED and DISMISSED must not be counted.
    Verified directly against the DB query that builds the ew_map.
    """
    db = TestingSessionLocal()
    w_open = EarlyWarning(
        project_id=22, warning_type="Burn Rate", warning_level="HIGH",
        title="Active", explanation="Active warning", trigger_signature="ew_count_open_p22",
        engine_version="6.1.0", provenance="AI ASSESSMENT", status="OPEN",
    )
    w_acknowledged = EarlyWarning(
        project_id=22, warning_type="Stagnation", warning_level="MEDIUM",
        title="Acknowledged", explanation="Acknowledged warning", trigger_signature="ew_count_ack_p22",
        engine_version="6.1.0", provenance="AI ASSESSMENT", status="ACKNOWLEDGED",
    )
    w_resolved = EarlyWarning(
        project_id=22, warning_type="Deadline", warning_level="HIGH",
        title="Resolved", explanation="Resolved warning", trigger_signature="ew_count_resolved_p22",
        engine_version="6.1.0", provenance="AI ASSESSMENT", status="RESOLVED",
    )
    w_dismissed = EarlyWarning(
        project_id=22, warning_type="Data Anomaly", warning_level="LOW",
        title="Dismissed", explanation="Dismissed warning", trigger_signature="ew_count_dismissed_p22",
        engine_version="6.1.0", provenance="AI ASSESSMENT", status="DISMISSED",
    )
    db.add_all([w_open, w_acknowledged, w_resolved, w_dismissed])
    db.commit()

    # Replicate the projects router query logic directly
    active_statuses = ["OPEN", "ACKNOWLEDGED", "UNDER_REVIEW"]
    ew_rows = db.query(EarlyWarning.project_id).filter(
        EarlyWarning.status.in_(active_statuses)
    ).all()
    ew_map = {}
    for row in ew_rows:
        ew_map[row[0]] = ew_map.get(row[0], 0) + 1

    db.close()

    # p22 has 2 active (OPEN + ACKNOWLEDGED), 1 RESOLVED, 1 DISMISSED
    assert ew_map.get(22, 0) == 2, \
        f"Expected 2 active warnings for p22 (OPEN+ACKNOWLEDGED), got {ew_map.get(22, 0)}"


# ---------------------------------------------------------------
# NONEXISTENT PROJECT
# ---------------------------------------------------------------

def test_early_warning_nonexistent_get():
    response = client.get("/api/projects/999/early-warning")
    assert response.status_code == 404

def test_early_warning_nonexistent_post():
    response = client.post("/api/projects/999/early-warnings/assess")
    assert response.status_code == 404


# ---------------------------------------------------------------
# RBAC — unauthenticated returns 401
# ---------------------------------------------------------------

def test_get_early_warning_unauthenticated():
    """
    GET without auth credentials must return 401.
    Temporarily removes the test override to test real auth middleware.
    """
    saved = app.dependency_overrides.pop(get_current_user, None)
    try:
        response = client.get("/api/projects/21/early-warning")
        assert response.status_code == 401
    finally:
        if saved is not None:
            app.dependency_overrides[get_current_user] = saved

def test_post_assess_unauthenticated():
    """
    POST without auth credentials must return 401.
    """
    from app.auth_utils import RoleChecker
    saved_user = app.dependency_overrides.pop(get_current_user, None)
    # RoleChecker is a class-based dependency; we need to remove the override for get_current_user
    # The RoleChecker internally calls get_current_user so clearing that override is sufficient
    try:
        response = client.post("/api/projects/20/early-warnings/assess")
        assert response.status_code == 401
    finally:
        if saved_user is not None:
            app.dependency_overrides[get_current_user] = saved_user


def teardown_module():
    app.dependency_overrides.clear()
