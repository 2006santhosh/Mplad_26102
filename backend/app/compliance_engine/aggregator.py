"""
Compliance Intelligence Engine — Aggregator

Runs all compliance checks against a project and produces
an aggregate assessment with coverage metrics.
"""

from typing import Dict, List, Any
from .checks import ALL_CHECKS

ENGINE_VERSION = "4.0.0"


class ComplianceAggregator:
    """Runs all compliance checks and aggregates results."""

    def assess(self, project: Dict) -> Dict:
        """
        Run all compliance checks against the project dictionary.

        Returns:
        {
            "overall_status": str,
            "coverage_percentage": float,
            "pass_count": int,
            "review_count": int,
            "not_assessable_count": int,
            "fail_count": int,
            "total_checks": int,
            "checks": [dict, ...],
            "engine_version": str,
        }
        """
        checks = []
        for check_fn in ALL_CHECKS:
            result = check_fn(project)
            checks.append(result)

        pass_count = sum(1 for c in checks if c["status"] == "PASS")
        review_count = sum(1 for c in checks if c["status"] == "REVIEW")
        not_assessable_count = sum(1 for c in checks if c["status"] == "NOT_ASSESSABLE")
        fail_count = sum(1 for c in checks if c["status"] == "FAIL")
        total = len(checks)

        assessable = pass_count + review_count + fail_count
        coverage = (assessable / total * 100) if total > 0 else 0.0

        # Determine overall status using the rules from the specification:
        # - If any FAIL exists → REVIEW (or FAIL if purely deterministic)
        # - If any REVIEW exists → REVIEW
        # - If all assessable checks PASS → PASS (possibly with limited coverage)
        # - If insufficient assessable checks → NOT_ASSESSABLE
        if fail_count > 0:
            overall = "REVIEW"
        elif review_count > 0:
            overall = "REVIEW"
        elif assessable == 0:
            overall = "NOT_ASSESSABLE"
        elif pass_count == assessable and coverage < 50:
            overall = "PASS WITH LIMITED COVERAGE"
        else:
            overall = "PASS"

        return {
            "overall_status": overall,
            "coverage_percentage": round(coverage, 1),
            "pass_count": pass_count,
            "review_count": review_count,
            "not_assessable_count": not_assessable_count,
            "fail_count": fail_count,
            "total_checks": total,
            "checks": checks,
            "engine_version": ENGINE_VERSION,
        }
