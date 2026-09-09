"""
Phase 4 — Comprehensive Compliance Engine Unit Tests

Tests the compliance engine directly (checks + aggregator) without
going through the API, covering all categories from the specification:

A. Field availability
B. Sanction validation
C. Stage validation
D. Temporal checks
E. Financial checks
F. Progress
G. Contractor
H. GPS
I. Compliance aggregation
J. Provenance
"""
import pytest
from datetime import date, timedelta
from app.compliance_engine.checks import (
    check_work_id_present,
    check_mp_info_present,
    check_state_district_present,
    check_category_present,
    check_sanction_amount_valid,
    check_work_stage_recognized,
    check_sanction_date_present,
    check_financial_discipline,
    check_stage_duration_review,
    check_contractor_verification,
    check_gps_verification,
    check_physical_progress_verification,
)
from app.compliance_engine.aggregator import ComplianceAggregator


def _make_project(**overrides):
    """Helper to create a project dict with sensible defaults."""
    base = {
        "id": 1,
        "work_id": "W001",
        "mp_id": 1,
        "mp_name": "Test MP",
        "state": "Test State",
        "district": "Test District",
        "constituency": "Test Constituency",
        "category": "Road",
        "work_category": "Normal/Others",
        "description": "Test work description",
        "sanctioned_amount": 100000,
        "expenditure": 50000,
        "work_stage": "Physical Inspection",
        "planned_start": date(2024, 1, 1),
        "planned_completion": date(2025, 1, 1),
        "actual_completion": None,
        "status": "IN_PROGRESS",
        "latitude": None,
        "longitude": None,
        "progress_pct": 40,
        "contractors": [],
        "source_type": "OFFICIAL",
    }
    base.update(overrides)
    return base


# ===================================================================
# A. Field Availability Tests
# ===================================================================

class TestFieldAvailability:
    def test_all_fields_present(self):
        p = _make_project()
        r = check_work_id_present(p)
        assert r["status"] == "PASS"
        assert r["provenance"] == "OFFICIAL"

    def test_missing_work_id(self):
        p = _make_project(work_id=None)
        r = check_work_id_present(p)
        assert r["status"] == "NOT_ASSESSABLE"
        assert r["provenance"] == "UNAVAILABLE"

    def test_empty_work_id(self):
        p = _make_project(work_id="  ")
        r = check_work_id_present(p)
        assert r["status"] == "NOT_ASSESSABLE"

    def test_mp_info_present(self):
        p = _make_project()
        r = check_mp_info_present(p)
        assert r["status"] == "PASS"

    def test_mp_info_missing(self):
        p = _make_project(mp_id=None, mp_name=None)
        r = check_mp_info_present(p)
        assert r["status"] == "NOT_ASSESSABLE"

    def test_state_district_both_present(self):
        p = _make_project()
        r = check_state_district_present(p)
        assert r["status"] == "PASS"

    def test_state_only(self):
        p = _make_project(district=None)
        r = check_state_district_present(p)
        assert r["status"] == "REVIEW"
        assert r["severity"] == "LOW"

    def test_state_district_both_missing(self):
        p = _make_project(state=None, district=None)
        r = check_state_district_present(p)
        assert r["status"] == "NOT_ASSESSABLE"

    def test_category_present(self):
        p = _make_project()
        r = check_category_present(p)
        assert r["status"] == "PASS"

    def test_category_missing(self):
        p = _make_project(category=None)
        r = check_category_present(p)
        assert r["status"] == "NOT_ASSESSABLE"

    def test_sanction_date_present(self):
        p = _make_project()
        r = check_sanction_date_present(p)
        assert r["status"] == "PASS"

    def test_sanction_date_missing(self):
        p = _make_project(planned_start=None)
        r = check_sanction_date_present(p)
        assert r["status"] == "NOT_ASSESSABLE"


# ===================================================================
# B. Sanction Validation Tests
# ===================================================================

class TestSanctionValidation:
    def test_valid_amount(self):
        p = _make_project(sanctioned_amount=500000)
        r = check_sanction_amount_valid(p)
        assert r["status"] == "PASS"
        assert r["provenance"] == "OFFICIAL"
        assert r["evidence"]["sanctioned_amount"] == 500000

    def test_zero_amount(self):
        p = _make_project(sanctioned_amount=0)
        r = check_sanction_amount_valid(p)
        assert r["status"] == "REVIEW"
        assert r["severity"] == "MEDIUM"

    def test_negative_amount(self):
        p = _make_project(sanctioned_amount=-5000)
        r = check_sanction_amount_valid(p)
        assert r["status"] == "FAIL"
        assert r["severity"] == "HIGH"

    def test_missing_amount(self):
        p = _make_project(sanctioned_amount=None)
        r = check_sanction_amount_valid(p)
        assert r["status"] == "NOT_ASSESSABLE"
        # Missing data MUST NEVER become PASS or FAIL
        assert r["status"] not in ("PASS", "FAIL")


# ===================================================================
# C. Stage Validation Tests
# ===================================================================

class TestStageValidation:
    def test_valid_stage(self):
        p = _make_project(work_stage="Physical Inspection")
        r = check_work_stage_recognized(p)
        assert r["status"] == "PASS"
        assert r["provenance"] == "OFFICIAL"

    def test_missing_stage(self):
        p = _make_project(work_stage=None)
        r = check_work_stage_recognized(p)
        assert r["status"] == "NOT_ASSESSABLE"

    def test_unknown_stage(self):
        p = _make_project(work_stage="Unknown Stage XYZ")
        r = check_work_stage_recognized(p)
        assert r["status"] == "REVIEW"
        assert r["severity"] == "LOW"


# ===================================================================
# D. Temporal Checks Tests
# ===================================================================

class TestTemporalChecks:
    def test_valid_recent_project(self):
        p = _make_project(planned_start=date.today() - timedelta(days=30))
        r = check_stage_duration_review(p)
        assert r["status"] == "PASS"
        assert r["provenance"] == "DERIVED"

    def test_missing_date(self):
        p = _make_project(planned_start=None)
        r = check_stage_duration_review(p)
        assert r["status"] == "NOT_ASSESSABLE"

    def test_long_duration(self):
        p = _make_project(planned_start=date.today() - timedelta(days=800))
        r = check_stage_duration_review(p)
        assert r["status"] == "REVIEW"
        assert r["severity"] == "HIGH"

    def test_medium_duration(self):
        p = _make_project(planned_start=date.today() - timedelta(days=400))
        r = check_stage_duration_review(p)
        assert r["status"] == "REVIEW"
        assert r["severity"] == "MEDIUM"

    def test_completed_project_skips_duration(self):
        p = _make_project(status="COMPLETED", planned_start=date(2020, 1, 1))
        r = check_stage_duration_review(p)
        assert r["status"] == "PASS"  # Completed → no duration concern


# ===================================================================
# E. Financial Checks Tests
# ===================================================================

class TestFinancialChecks:
    def test_expenditure_within_bounds(self):
        p = _make_project(sanctioned_amount=100000, expenditure=50000)
        r = check_financial_discipline(p)
        assert r["status"] == "PASS"

    def test_expenditure_exceeds(self):
        p = _make_project(sanctioned_amount=100000, expenditure=150000)
        r = check_financial_discipline(p)
        assert r["status"] == "REVIEW"
        assert r["severity"] == "HIGH"

    def test_negative_expenditure(self):
        p = _make_project(expenditure=-500)
        r = check_financial_discipline(p)
        assert r["status"] == "FAIL"  # Deterministic data-integrity rule

    def test_missing_expenditure(self):
        p = _make_project(expenditure=None)
        r = check_financial_discipline(p)
        assert r["status"] == "NOT_ASSESSABLE"
        # Missing data MUST NEVER become PASS or FAIL
        assert r["status"] not in ("PASS", "FAIL")

    def test_missing_sanction_with_expenditure(self):
        p = _make_project(sanctioned_amount=None, expenditure=5000)
        r = check_financial_discipline(p)
        assert r["status"] == "NOT_ASSESSABLE"


# ===================================================================
# F. Progress Tests
# ===================================================================

class TestProgress:
    def test_physical_progress_always_not_assessable(self):
        """Analytical Progress Proxy is never directly official."""
        p = _make_project(progress_pct=40)
        r = check_physical_progress_verification(p)
        assert r["status"] == "NOT_ASSESSABLE"
        assert r["rule_type"] == "UNAVAILABLE"

    def test_proxy_mentioned_in_evidence(self):
        p = _make_project(progress_pct=40, work_stage="Physical Inspection")
        r = check_physical_progress_verification(p)
        assert r["evidence"].get("analytical_proxy_pct") == 40
        assert r["evidence"].get("proxy_source") == "DERIVED from WORK_STAGE"


# ===================================================================
# G. Contractor Tests
# ===================================================================

class TestContractor:
    def test_contractor_unavailable(self):
        p = _make_project(contractors=[], source_type="OFFICIAL")
        r = check_contractor_verification(p)
        assert r["status"] == "NOT_ASSESSABLE"
        assert r["rule_type"] == "UNAVAILABLE"

    def test_contractor_not_assessable_not_pass_or_fail(self):
        """Missing contractor MUST NOT become PASS or FAIL."""
        p = _make_project(contractors=[], source_type="OFFICIAL")
        r = check_contractor_verification(p)
        assert r["status"] not in ("PASS", "FAIL")


# ===================================================================
# H. GPS Tests
# ===================================================================

class TestGPS:
    def test_gps_null_coordinates(self):
        p = _make_project(latitude=None, longitude=None)
        r = check_gps_verification(p)
        assert r["status"] == "NOT_ASSESSABLE"
        assert r["rule_type"] == "UNAVAILABLE"

    def test_gps_not_assessable_not_pass_or_fail(self):
        """Missing GPS MUST NOT become PASS or FAIL."""
        p = _make_project(latitude=None, longitude=None)
        r = check_gps_verification(p)
        assert r["status"] not in ("PASS", "FAIL")


# ===================================================================
# I. Compliance Aggregation Tests
# ===================================================================

class TestAggregation:
    def test_all_pass_project(self):
        p = _make_project(planned_start=date.today() - timedelta(days=30))
        agg = ComplianceAggregator()
        result = agg.assess(p)
        assert result["total_checks"] == 12
        assert result["pass_count"] + result["review_count"] + result["not_assessable_count"] + result["fail_count"] == 12
        assert result["engine_version"] is not None

    def test_pass_plus_review(self):
        p = _make_project(sanctioned_amount=100000, expenditure=150000)
        agg = ComplianceAggregator()
        result = agg.assess(p)
        assert result["review_count"] >= 1
        assert result["overall_status"] == "REVIEW"

    def test_pass_plus_not_assessable(self):
        """Mix of PASS and NOT_ASSESSABLE should be handled honestly."""
        p = _make_project()
        agg = ComplianceAggregator()
        result = agg.assess(p)
        # At minimum GPS, contractor, physical_progress are NOT_ASSESSABLE
        assert result["not_assessable_count"] >= 3
        assert result["coverage_percentage"] < 100

    def test_all_not_assessable(self):
        """Project with almost nothing available."""
        p = {
            "id": 99,
            "work_id": None,
            "mp_id": None,
            "mp_name": None,
            "state": None,
            "district": None,
            "constituency": None,
            "category": None,
            "sanctioned_amount": None,
            "work_stage": None,
            "planned_start": None,
            "expenditure": None,
            "latitude": None,
            "longitude": None,
            "progress_pct": None,
            "contractors": [],
            "source_type": "OFFICIAL",
            "status": None,
        }
        agg = ComplianceAggregator()
        result = agg.assess(p)
        assert result["not_assessable_count"] == 12
        assert result["pass_count"] == 0
        assert result["overall_status"] == "NOT_ASSESSABLE"
        assert result["coverage_percentage"] == 0.0

    def test_coverage_calculation(self):
        p = _make_project()
        agg = ComplianceAggregator()
        result = agg.assess(p)
        assessable = result["pass_count"] + result["review_count"] + result["fail_count"]
        expected = round(assessable / result["total_checks"] * 100, 1)
        assert result["coverage_percentage"] == expected


# ===================================================================
# J. Provenance Tests
# ===================================================================

class TestProvenance:
    def test_official_provenance(self):
        p = _make_project()
        r = check_work_id_present(p)
        assert r["provenance"] == "OFFICIAL"

    def test_derived_provenance(self):
        p = _make_project(planned_start=date.today() - timedelta(days=30))
        r = check_stage_duration_review(p)
        assert r["provenance"] == "DERIVED"

    def test_unavailable_provenance(self):
        p = _make_project(latitude=None, longitude=None)
        r = check_gps_verification(p)
        assert r["provenance"] == "UNAVAILABLE"

    def test_check_contract_structure(self):
        """Every check must have the full contract."""
        p = _make_project()
        required_keys = {
            "check_id", "check_name", "status", "severity",
            "explanation", "evidence", "provenance",
            "required_fields", "available_fields", "rule_type"
        }
        for check_fn in [
            check_work_id_present, check_mp_info_present,
            check_state_district_present, check_category_present,
            check_sanction_amount_valid, check_work_stage_recognized,
            check_sanction_date_present, check_financial_discipline,
            check_stage_duration_review, check_contractor_verification,
            check_gps_verification, check_physical_progress_verification,
        ]:
            result = check_fn(p)
            assert required_keys.issubset(result.keys()), f"{check_fn.__name__} missing keys: {required_keys - result.keys()}"
