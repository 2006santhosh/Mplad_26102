"""
Phase 4 — Updated compliance tests for the new ComplianceAssessmentResponse schema.

These tests validate the API endpoint behavior with the new Phase 4
compliance contract (check_id, provenance, rule_type, etc.)
"""
from fastapi.testclient import TestClient
from app.main import app
from app.database import get_db
from app.auth_utils import get_current_user, RoleChecker
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
from app.models import Base, Project, DataSource, MP, ProjectProgress, ProjectFinancials
from datetime import date
import pytest

# Use an in-memory SQLite database for fast testing
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

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()

    # DataSource and MP for FK constraints
    ds = DataSource(id=1, source_name="Test", source_type="OFFICIAL")
    mp = MP(id=1, data_source_id=1, name="Test MP", state="Test State")
    db.add_all([ds, mp])
    db.commit()

    # Project 1: Valid and compliant
    p1 = Project(id=1, mp_id=1, data_source_id=1, category="Road",
                 sanctioned_amount=10000, status="ONGOING",
                 work_id="W001", work_stage="Physical Inspection",
                 district="Test District", planned_start=date(2024, 1, 1))
    f1 = ProjectFinancials(project_id=1, expenditure=5000)
    pr1 = ProjectProgress(project_id=1, percentage=50, reported_at=date.today())

    # Project 2: Expenditure > Sanctioned
    p2 = Project(id=2, mp_id=1, data_source_id=1, category="Water",
                 sanctioned_amount=10000, status="ONGOING",
                 work_id="W002", work_stage="Physical Inspection",
                 district="Test District", planned_start=date(2024, 1, 1))
    f2 = ProjectFinancials(project_id=2, expenditure=15000)

    # Project 3: Completed but <100% progress (progress is DERIVED proxy)
    p3 = Project(id=3, mp_id=1, data_source_id=1, category="School",
                 sanctioned_amount=20000, status="COMPLETED",
                 work_id="W003", work_stage="Work Completed",
                 district="Test District", planned_start=date(2024, 1, 1))
    pr3 = ProjectProgress(project_id=3, percentage=90, reported_at=date.today())

    # Project 4: Missing financial data
    p4 = Project(id=4, mp_id=1, data_source_id=1, category="Hospital",
                 sanctioned_amount=50000, status="ONGOING",
                 work_id="W004", work_stage="Sanction",
                 district="Test District", planned_start=date(2024, 1, 1))

    # Project 5: Completed + missing progress
    p5 = Project(id=5, mp_id=1, data_source_id=1, category="Park",
                 sanctioned_amount=5000, status="COMPLETED",
                 work_id="W005", work_stage="Work Completed",
                 district="Test District", planned_start=date(2024, 1, 1))

    # Project 6: Invalid/negative values
    p6 = Project(id=6, mp_id=1, data_source_id=1, category="Road",
                 sanctioned_amount=-50, status="COMPLETED",
                 work_id="W006", work_stage="Work Completed",
                 district="Test District", planned_start=date(2024, 1, 1))
    f6 = ProjectFinancials(project_id=6, expenditure=-100)
    pr6 = ProjectProgress(project_id=6, percentage=150, reported_at=date.today())

    db.add_all([p1, f1, pr1, p2, f2, p3, pr3, p4, p5, p6, f6, pr6])
    db.commit()
    db.close()


def test_compliance_valid_project():
    """Project 1 has all required fields → mostly PASS, some NOT_ASSESSABLE."""
    response = client.get("/api/projects/1/compliance/")
    assert response.status_code == 200
    data = response.json()
    assert "checks" in data
    assert data["total_checks"] == 12
    assert data["engine_version"] is not None

    # Verify structure of each check
    for check in data["checks"]:
        assert "check_id" in check
        assert "check_name" in check
        assert check["status"] in ("PASS", "REVIEW", "NOT_ASSESSABLE", "FAIL")
        assert "provenance" in check
        assert "rule_type" in check

    # Financial discipline should PASS (expenditure 5000 <= sanctioned 10000)
    fin_check = next(c for c in data["checks"] if c["check_id"] == "financial_discipline")
    assert fin_check["status"] == "PASS"

    # Work ID should PASS
    wid_check = next(c for c in data["checks"] if c["check_id"] == "work_id_present")
    assert wid_check["status"] == "PASS"
    assert wid_check["provenance"] == "OFFICIAL"

    # GPS should be NOT_ASSESSABLE
    gps_check = next(c for c in data["checks"] if c["check_id"] == "gps_verification")
    assert gps_check["status"] == "NOT_ASSESSABLE"

    # Contractor should be NOT_ASSESSABLE
    cont_check = next(c for c in data["checks"] if c["check_id"] == "contractor_verification")
    assert cont_check["status"] == "NOT_ASSESSABLE"


def test_compliance_expenditure_exceeds():
    """Project 2 has expenditure > sanctioned → financial discipline REVIEW."""
    response = client.get("/api/projects/2/compliance/")
    assert response.status_code == 200
    data = response.json()
    fin_check = next(c for c in data["checks"] if c["check_id"] == "financial_discipline")
    assert fin_check["status"] == "REVIEW"
    assert fin_check["severity"] == "HIGH"
    assert data["overall_status"] == "REVIEW"


def test_compliance_completed_project():
    """Project 3 is completed → stage duration passes, coverage measured."""
    response = client.get("/api/projects/3/compliance/")
    assert response.status_code == 200
    data = response.json()

    # Stage duration for completed project should PASS
    dur_check = next(c for c in data["checks"] if c["check_id"] == "stage_duration_review")
    assert dur_check["status"] == "PASS"


def test_compliance_missing_financial():
    """Project 4 has no financial data → financial discipline NOT_ASSESSABLE."""
    response = client.get("/api/projects/4/compliance/")
    assert response.status_code == 200
    data = response.json()
    fin_check = next(c for c in data["checks"] if c["check_id"] == "financial_discipline")
    assert fin_check["status"] == "NOT_ASSESSABLE"
    assert "unavailable" in fin_check["explanation"].lower() or "not" in fin_check["explanation"].lower()


def test_compliance_completed_missing_progress():
    """Project 5 is completed without progress → physical progress always NOT_ASSESSABLE."""
    response = client.get("/api/projects/5/compliance/")
    assert response.status_code == 200
    data = response.json()
    prog_check = next(c for c in data["checks"] if c["check_id"] == "physical_progress_verification")
    assert prog_check["status"] == "NOT_ASSESSABLE"
    assert prog_check["rule_type"] == "UNAVAILABLE"


def test_compliance_invalid_values():
    """Project 6 has negative sanction and negative expenditure."""
    response = client.get("/api/projects/6/compliance/")
    assert response.status_code == 200
    data = response.json()
    # Negative sanctioned amount → FAIL (deterministic data-integrity)
    sanc_check = next(c for c in data["checks"] if c["check_id"] == "sanction_amount_valid")
    assert sanc_check["status"] == "FAIL"
    assert sanc_check["severity"] == "HIGH"

    # Negative expenditure → FAIL
    fin_check = next(c for c in data["checks"] if c["check_id"] == "financial_discipline")
    assert fin_check["status"] == "FAIL"


def test_compliance_nonexistent_project():
    response = client.get("/api/projects/999/compliance/")
    assert response.status_code == 404


def test_compliance_coverage_percentage():
    """Verify coverage percentage is correctly calculated."""
    response = client.get("/api/projects/1/compliance/")
    assert response.status_code == 200
    data = response.json()
    assert 0 <= data["coverage_percentage"] <= 100
    assessable = data["pass_count"] + data["review_count"] + data["fail_count"]
    expected_coverage = round(assessable / data["total_checks"] * 100, 1)
    assert data["coverage_percentage"] == expected_coverage


def test_compliance_post_assess():
    """POST /assess creates a new assessment."""
    response = client.post("/api/projects/1/compliance/assess")
    assert response.status_code == 200
    data = response.json()
    assert data["project_id"] == 1
    assert data["total_checks"] == 12
    assert data["engine_version"] is not None


def setup_module():
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: {'sub': 'test', 'role': 'Admin'}
    app.dependency_overrides[RoleChecker(["Admin", "Auditor", "State", "District"])] = lambda: {'sub': 'test', 'role': 'Admin'}

def teardown_module():
    app.dependency_overrides.clear()
