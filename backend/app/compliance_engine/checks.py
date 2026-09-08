"""
Compliance Intelligence Engine — Individual Check Functions

Every check returns a standardized contract dict:
{
    "check_id": str,
    "check_name": str,
    "status": "PASS" | "REVIEW" | "NOT_ASSESSABLE" | "FAIL",
    "severity": "NONE" | "LOW" | "MEDIUM" | "HIGH" | "NOT_AVAILABLE",
    "explanation": str,
    "evidence": dict,
    "provenance": str,       # OFFICIAL, DERIVED, ANALYTICAL, UNAVAILABLE
    "required_fields": [str],
    "available_fields": [str],
    "rule_type": str          # SYSTEM_VALIDATION, ANALYTICAL_CHECK, UNAVAILABLE
}

RULES:
- Missing data MUST NEVER become PASS or FAIL.
- FAIL is used only for deterministic data-integrity violations.
- REVIEW is used for analytical concerns.
- NOT_ASSESSABLE is used when required data is absent.
- No OFFICIAL_RULE classification in this phase.
"""

import pandas as pd
from datetime import date
from typing import Dict, Any, Optional

# ---------------------------------------------------------------------------
# Known official work stages from the eSAKSHI dataset
# ---------------------------------------------------------------------------
KNOWN_STAGES = {
    "Sanction",
    "Time Estimation",
    "Vendor Identification",
    "Physical Inspection",
    "Work partially Completed",
    "Work Completed",
}


def _base(check_id: str, check_name: str, rule_type: str,
          required_fields: list, status: str = "NOT_ASSESSABLE",
          severity: str = "NOT_AVAILABLE") -> Dict:
    """Build a baseline check result."""
    return {
        "check_id": check_id,
        "check_name": check_name,
        "status": status,
        "severity": severity,
        "explanation": "",
        "evidence": {},
        "provenance": "UNAVAILABLE",
        "required_fields": required_fields,
        "available_fields": [],
        "rule_type": rule_type,
    }


# ===================================================================
# DATA INTEGRITY — checks 1-7
# ===================================================================

def check_work_id_present(project: Dict) -> Dict:
    """Check 1: Work ID is present and non-empty."""
    r = _base("work_id_present", "Work ID Availability",
              "SYSTEM_VALIDATION", ["work_id"])
    wid = project.get("work_id")
    if wid and str(wid).strip():
        r["status"] = "PASS"
        r["severity"] = "NONE"
        r["explanation"] = "Official Work ID is present."
        r["evidence"] = {"work_id": str(wid).strip()}
        r["provenance"] = "OFFICIAL"
        r["available_fields"] = ["work_id"]
    else:
        r["status"] = "NOT_ASSESSABLE"
        r["severity"] = "NOT_AVAILABLE"
        r["explanation"] = "Work ID is missing from the official record."
        r["provenance"] = "UNAVAILABLE"
    return r


def check_mp_info_present(project: Dict) -> Dict:
    """Check 2: MP information is linked and available."""
    r = _base("mp_info_present", "MP Information Availability",
              "SYSTEM_VALIDATION", ["mp_id", "mp_name"])
    mp_id = project.get("mp_id")
    mp_name = project.get("mp_name")
    available = []
    if mp_id:
        available.append("mp_id")
    if mp_name and str(mp_name).strip():
        available.append("mp_name")
    r["available_fields"] = available
    if mp_id and mp_name and str(mp_name).strip():
        r["status"] = "PASS"
        r["severity"] = "NONE"
        r["explanation"] = "MP information is available."
        r["evidence"] = {"mp_id": mp_id, "mp_name": str(mp_name).strip()}
        r["provenance"] = "OFFICIAL"
    else:
        r["status"] = "NOT_ASSESSABLE"
        r["severity"] = "NOT_AVAILABLE"
        r["explanation"] = "MP information is missing or incomplete."
        r["provenance"] = "UNAVAILABLE"
    return r


def check_state_district_present(project: Dict) -> Dict:
    """Check 3: State and district fields are populated."""
    r = _base("state_district_present", "Administrative Location Available",
              "SYSTEM_VALIDATION", ["state", "district"])
    state = project.get("state") or ""
    district = project.get("district") or ""
    available = []
    evidence = {}
    if state.strip():
        available.append("state")
        evidence["state"] = state.strip()
    if district.strip():
        available.append("district")
        evidence["district"] = district.strip()
    r["available_fields"] = available
    r["evidence"] = evidence
    if state.strip() and district.strip():
        r["status"] = "PASS"
        r["severity"] = "NONE"
        r["explanation"] = "State and district information are available."
        r["provenance"] = "OFFICIAL"
    elif state.strip() or district.strip():
        r["status"] = "REVIEW"
        r["severity"] = "LOW"
        r["explanation"] = "Partial administrative location data available."
        r["provenance"] = "OFFICIAL"
    else:
        r["status"] = "NOT_ASSESSABLE"
        r["severity"] = "NOT_AVAILABLE"
        r["explanation"] = "Administrative location data is unavailable."
        r["provenance"] = "UNAVAILABLE"
    return r


def check_category_present(project: Dict) -> Dict:
    """Check 4: Work category/activity name is present."""
    r = _base("category_present", "Work Category Available",
              "SYSTEM_VALIDATION", ["category"])
    cat = project.get("category") or ""
    if cat.strip():
        r["status"] = "PASS"
        r["severity"] = "NONE"
        r["explanation"] = "Work category is available."
        r["evidence"] = {"category": cat.strip()}
        r["provenance"] = "OFFICIAL"
        r["available_fields"] = ["category"]
    else:
        r["status"] = "NOT_ASSESSABLE"
        r["severity"] = "NOT_AVAILABLE"
        r["explanation"] = "Work category is missing from the official record."
        r["provenance"] = "UNAVAILABLE"
    return r


def check_sanction_amount_valid(project: Dict) -> Dict:
    """Check 5: Sanction amount exists, is numeric, and is non-negative."""
    r = _base("sanction_amount_valid", "Sanction Amount Validation",
              "SYSTEM_VALIDATION", ["sanctioned_amount"])
    amt = project.get("sanctioned_amount")
    if amt is None or (isinstance(amt, float) and pd.isna(amt)):
        r["status"] = "NOT_ASSESSABLE"
        r["severity"] = "NOT_AVAILABLE"
        r["explanation"] = "Sanctioned amount is not available in the official record."
        r["provenance"] = "UNAVAILABLE"
        return r
    try:
        amt_f = float(amt)
    except (ValueError, TypeError):
        r["status"] = "REVIEW"
        r["severity"] = "MEDIUM"
        r["explanation"] = "Sanctioned amount is not a valid numeric value."
        r["evidence"] = {"raw_value": str(amt)}
        r["provenance"] = "OFFICIAL"
        r["available_fields"] = ["sanctioned_amount"]
        return r
    r["available_fields"] = ["sanctioned_amount"]
    if amt_f < 0:
        r["status"] = "FAIL"
        r["severity"] = "HIGH"
        r["explanation"] = "Sanctioned amount is negative, which fails basic data-integrity validation."
        r["evidence"] = {"sanctioned_amount": amt_f}
        r["provenance"] = "OFFICIAL"
    elif amt_f == 0:
        r["status"] = "REVIEW"
        r["severity"] = "MEDIUM"
        r["explanation"] = "Sanctioned amount is zero. Review recommended."
        r["evidence"] = {"sanctioned_amount": 0}
        r["provenance"] = "OFFICIAL"
    else:
        r["status"] = "PASS"
        r["severity"] = "NONE"
        r["explanation"] = "Sanctioned amount is valid and positive."
        r["evidence"] = {"sanctioned_amount": amt_f}
        r["provenance"] = "OFFICIAL"
    return r


def check_work_stage_recognized(project: Dict) -> Dict:
    """Check 6: Work stage matches a known official vocabulary."""
    r = _base("work_stage_recognized", "Work Stage Validation",
              "SYSTEM_VALIDATION", ["work_stage"])
    stage = project.get("work_stage") or ""
    if not stage.strip():
        r["status"] = "NOT_ASSESSABLE"
        r["severity"] = "NOT_AVAILABLE"
        r["explanation"] = "Work stage is missing from the official record."
        r["provenance"] = "UNAVAILABLE"
        return r
    stage = stage.strip()
    r["available_fields"] = ["work_stage"]
    r["evidence"] = {"work_stage": stage, "known_stages": sorted(KNOWN_STAGES)}
    r["provenance"] = "OFFICIAL"
    if stage in KNOWN_STAGES:
        r["status"] = "PASS"
        r["severity"] = "NONE"
        r["explanation"] = f"Work stage '{stage}' is a recognized official stage."
    else:
        r["status"] = "REVIEW"
        r["severity"] = "LOW"
        r["explanation"] = f"Work stage '{stage}' is not in the known stage vocabulary. Review recommended."
    return r


def check_sanction_date_present(project: Dict) -> Dict:
    """Check 7: Sanction / planned start date is available."""
    r = _base("sanction_date_present", "Sanction Date Availability",
              "SYSTEM_VALIDATION", ["planned_start"])
    d = project.get("planned_start")
    if d and d is not None:
        r["status"] = "PASS"
        r["severity"] = "NONE"
        r["explanation"] = "Sanction / planned start date is available."
        r["evidence"] = {"planned_start": str(d)}
        r["provenance"] = "OFFICIAL"
        r["available_fields"] = ["planned_start"]
    else:
        r["status"] = "NOT_ASSESSABLE"
        r["severity"] = "NOT_AVAILABLE"
        r["explanation"] = "Sanction date is not available in the official record."
        r["provenance"] = "UNAVAILABLE"
    return r


# ===================================================================
# FINANCIAL — check 8
# ===================================================================

def check_financial_discipline(project: Dict) -> Dict:
    """Check 8: Expenditure ≤ sanctioned amount, where data is available."""
    r = _base("financial_discipline", "Financial Discipline Check",
              "SYSTEM_VALIDATION", ["sanctioned_amount", "expenditure"])
    amt = project.get("sanctioned_amount")
    exp = project.get("expenditure")

    available = []
    if amt is not None and not (isinstance(amt, float) and pd.isna(amt)):
        available.append("sanctioned_amount")
    if exp is not None and not (isinstance(exp, float) and pd.isna(exp)):
        available.append("expenditure")
    r["available_fields"] = available

    # If expenditure is unavailable → NOT_ASSESSABLE (never assume zero)
    if "expenditure" not in available:
        r["status"] = "NOT_ASSESSABLE"
        r["severity"] = "NOT_AVAILABLE"
        r["explanation"] = "Expenditure data is unavailable in the official record."
        r["provenance"] = "UNAVAILABLE"
        return r

    try:
        exp_f = float(exp)
    except (ValueError, TypeError):
        r["status"] = "NOT_ASSESSABLE"
        r["severity"] = "NOT_AVAILABLE"
        r["explanation"] = "Expenditure value is not a valid number."
        return r

    # Negative expenditure → FAIL (deterministic data-integrity rule)
    if exp_f < 0:
        r["status"] = "FAIL"
        r["severity"] = "HIGH"
        r["explanation"] = "Expenditure is negative, which fails basic data-integrity validation."
        r["evidence"] = {"expenditure": exp_f}
        r["provenance"] = "OFFICIAL"
        return r

    # If sanctioned amount is unavailable, we can only validate expenditure non-negativity
    if "sanctioned_amount" not in available:
        r["status"] = "NOT_ASSESSABLE"
        r["severity"] = "NOT_AVAILABLE"
        r["explanation"] = "Cannot verify financial discipline without a valid sanctioned amount."
        r["evidence"] = {"expenditure": exp_f}
        r["provenance"] = "OFFICIAL"
        return r

    try:
        amt_f = float(amt)
    except (ValueError, TypeError):
        r["status"] = "NOT_ASSESSABLE"
        r["severity"] = "NOT_AVAILABLE"
        r["explanation"] = "Sanctioned amount is not a valid number."
        return r

    if amt_f <= 0:
        r["status"] = "NOT_ASSESSABLE"
        r["severity"] = "NOT_AVAILABLE"
        r["explanation"] = "Cannot verify financial discipline with zero or negative sanctioned amount."
        r["evidence"] = {"sanctioned_amount": amt_f, "expenditure": exp_f}
        r["provenance"] = "OFFICIAL"
        return r

    r["evidence"] = {"sanctioned_amount": amt_f, "expenditure": exp_f}
    r["provenance"] = "OFFICIAL"

    if exp_f > amt_f:
        r["status"] = "REVIEW"
        r["severity"] = "HIGH"
        r["explanation"] = f"Recorded expenditure (₹{exp_f:,.0f}) exceeds the sanctioned amount (₹{amt_f:,.0f}). Review recommended."
    else:
        r["status"] = "PASS"
        r["severity"] = "NONE"
        r["explanation"] = "Expenditure is within sanctioned bounds."
    return r


# ===================================================================
# IMPLEMENTATION MONITORING — check 9
# ===================================================================

def check_stage_duration_review(project: Dict) -> Dict:
    """Check 9: Analytical duration review based on elapsed time at current stage."""
    r = _base("stage_duration_review", "Analytical Duration Review",
              "ANALYTICAL_CHECK", ["planned_start", "work_stage", "status"])
    s_date = project.get("planned_start")
    stage = project.get("work_stage") or ""
    status = project.get("status") or ""

    available = []
    if s_date:
        available.append("planned_start")
    if stage.strip():
        available.append("work_stage")
    if status.strip():
        available.append("status")
    r["available_fields"] = available

    if not s_date:
        r["status"] = "NOT_ASSESSABLE"
        r["severity"] = "NOT_AVAILABLE"
        r["explanation"] = "Sanction date is unavailable; cannot compute elapsed duration."
        r["provenance"] = "UNAVAILABLE"
        return r

    if status.upper() in ("COMPLETED",):
        r["status"] = "PASS"
        r["severity"] = "NONE"
        r["explanation"] = "Project is completed. Duration review not applicable."
        r["provenance"] = "DERIVED"
        r["evidence"] = {"status": status}
        return r

    try:
        if isinstance(s_date, date):
            start = s_date
        else:
            from datetime import datetime as _dt
            start = _dt.strptime(str(s_date), "%Y-%m-%d").date()
        elapsed = (date.today() - start).days
    except Exception:
        r["status"] = "NOT_ASSESSABLE"
        r["severity"] = "NOT_AVAILABLE"
        r["explanation"] = "Cannot parse sanction date for duration analysis."
        r["provenance"] = "UNAVAILABLE"
        return r

    r["provenance"] = "DERIVED"
    r["evidence"] = {
        "sanction_date": str(s_date),
        "elapsed_days": elapsed,
        "current_stage": stage or "Unknown",
        "note": "System-defined analytical threshold, not an official government deadline."
    }

    if elapsed > 730:  # > 2 years
        r["status"] = "REVIEW"
        r["severity"] = "HIGH"
        r["explanation"] = f"Project has been active for {elapsed} days ({elapsed // 365} years). Analytical duration review recommended."
    elif elapsed > 365:  # > 1 year
        r["status"] = "REVIEW"
        r["severity"] = "MEDIUM"
        r["explanation"] = f"Project has been active for {elapsed} days. Analytical duration review recommended."
    else:
        r["status"] = "PASS"
        r["severity"] = "NONE"
        r["explanation"] = f"Project duration ({elapsed} days) is within analytical norms."
    return r


# ===================================================================
# UNAVAILABLE DATA — checks 10-12
# ===================================================================

def check_contractor_verification(project: Dict) -> Dict:
    """Check 10: Contractor information is unavailable in the official dataset."""
    r = _base("contractor_verification", "Contractor Information Check",
              "UNAVAILABLE", ["contractor_name", "contractor_id"])
    contractors = project.get("contractors", [])
    # For official eSAKSHI records, contractor data is not in the dataset.
    # Only synthetic records might have contractor links.
    source_type = project.get("source_type", "")
    if source_type == "SYNTHETIC" and contractors:
        r["status"] = "PASS"
        r["severity"] = "NONE"
        r["explanation"] = "Contractor information is available (synthetic demo data)."
        r["provenance"] = "SYNTHETIC"
        r["available_fields"] = ["contractor_id"]
        r["evidence"] = {"contractor_count": len(contractors)}
    else:
        r["status"] = "NOT_ASSESSABLE"
        r["severity"] = "NOT_AVAILABLE"
        r["explanation"] = "Contractor information is unavailable in the official dataset."
        r["provenance"] = "UNAVAILABLE"
    return r


def check_gps_verification(project: Dict) -> Dict:
    """Check 11: GPS coordinates are unavailable in the official dataset."""
    r = _base("gps_verification", "GPS Coordinate Verification",
              "UNAVAILABLE", ["latitude", "longitude"])
    lat = project.get("latitude")
    lon = project.get("longitude")
    if lat is not None and lon is not None and not (isinstance(lat, float) and pd.isna(lat)):
        r["status"] = "PASS"
        r["severity"] = "NONE"
        r["explanation"] = "GPS coordinates are available."
        r["provenance"] = "OFFICIAL"
        r["available_fields"] = ["latitude", "longitude"]
        r["evidence"] = {"latitude": lat, "longitude": lon}
    else:
        r["status"] = "NOT_ASSESSABLE"
        r["severity"] = "NOT_AVAILABLE"
        r["explanation"] = "Street-level GPS coordinates are unavailable in the official dataset."
        r["provenance"] = "UNAVAILABLE"
    return r


def check_physical_progress_verification(project: Dict) -> Dict:
    """Check 12: Physical progress % is unavailable — proxy is DERIVED."""
    r = _base("physical_progress_verification",
              "Physical Progress Verification",
              "UNAVAILABLE", ["physical_progress_pct"])
    # Physical progress percentage is never directly available in official data.
    # The system uses an analytical proxy derived from WORK_STAGE.
    progress = project.get("progress_pct")
    stage = project.get("work_stage") or ""
    r["status"] = "NOT_ASSESSABLE"
    r["severity"] = "NOT_AVAILABLE"
    r["explanation"] = "Physical progress percentage is unavailable in the official dataset. The system uses an analytical proxy derived from WORK_STAGE."
    r["provenance"] = "UNAVAILABLE"
    r["evidence"] = {}
    if progress is not None:
        r["evidence"]["analytical_proxy_pct"] = progress
        r["evidence"]["proxy_source"] = "DERIVED from WORK_STAGE"
    if stage.strip():
        r["evidence"]["work_stage"] = stage.strip()
    return r


# ===================================================================
# Master list of all checks
# ===================================================================

ALL_CHECKS = [
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
]
