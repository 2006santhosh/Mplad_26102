from typing import Any, Iterable


def calculate_review_priority(
    overall_risk: dict[str, Any],
    risk_trend: dict[str, Any],
    compliance: dict[str, Any],
    open_warnings: Iterable[Any],
    completion_risk: dict[str, Any],
) -> dict[str, Any]:
    def warning_value(warning: Any, attribute: str, key: str) -> Any:
        if isinstance(warning, dict):
            return warning.get(key)
        return getattr(warning, attribute)

    priority_level = "LOW"
    contributing_signals: list[str] = []
    why_flagged: list[dict[str, Any]] = []

    risk_level = overall_risk.get("level")
    if risk_level in ["HIGH", "CRITICAL"]:
        priority_level = "HIGH" if risk_level == "HIGH" else "CRITICAL"
        contributing_signals.append(f"{risk_level} current risk")
        why_flagged.append({
            "signal_type": "Current Risk",
            "severity": risk_level,
            "explanation": "The project currently exhibits elevated risk factors.",
            "evidence": {"score": overall_risk.get("score")},
            "provenance": "AI ASSESSMENT",
        })

    if risk_trend.get("trend") == "INCREASING":
        if priority_level in ["LOW", "MEDIUM"]:
            priority_level = "HIGH"
        contributing_signals.append("INCREASING risk trend")
        why_flagged.append({
            "signal_type": "Risk Trend",
            "severity": "HIGH",
            "explanation": risk_trend.get("explanation", "Risk is increasing."),
            "evidence": {"trend": "INCREASING"},
            "provenance": "AI ASSESSMENT",
        })

    compliance_status = compliance.get("status")
    if compliance_status in ["FAIL", "REVIEW"]:
        if priority_level in ["LOW", "MEDIUM"]:
            priority_level = "HIGH"
        contributing_signals.append(f"Compliance {compliance_status}")
        why_flagged.append({
            "signal_type": "Compliance",
            "severity": "HIGH" if compliance_status == "FAIL" else "MEDIUM",
            "explanation": "Compliance checks have flagged potential issues.",
            "evidence": {
                "fails": compliance.get("fail_count"),
                "reviews": compliance.get("review_count"),
            },
            "provenance": "AI ASSESSMENT",
        })

    warnings = list(open_warnings)
    if warnings:
        if any(warning_value(w, "warning_level", "level") == "CRITICAL" for w in warnings):
            priority_level = "CRITICAL"
        elif priority_level in ["LOW", "MEDIUM"]:
            priority_level = "HIGH"
        contributing_signals.append(f"{len(warnings)} open early warnings")
        for warning in warnings:
            level = warning_value(warning, "warning_level", "level")
            if level in ["HIGH", "CRITICAL"]:
                warning_type = warning_value(warning, "warning_type", "type")
                explanation = warning_value(warning, "explanation", "explanation")
                provenance = warning_value(warning, "provenance", "provenance")
                why_flagged.append({
                    "signal_type": "Early Warning",
                    "severity": level,
                    "explanation": explanation,
                    "evidence": {"type": warning_type},
                    "provenance": provenance,
                })

    completion_level = completion_risk.get("level")
    if completion_level in ["HIGH", "CRITICAL"]:
        if priority_level in ["LOW", "MEDIUM"]:
            priority_level = "HIGH"
        contributing_signals.append(f"{completion_level} completion risk")
        why_flagged.append({
            "signal_type": "Predictive Completion",
            "severity": completion_level,
            "explanation": "Predictive assessment indicates a risk of non-completion or delay.",
            "evidence": {"confidence": completion_risk.get("confidence")},
            "provenance": "AI ASSESSMENT",
        })

    if priority_level == "LOW" and risk_level == "MEDIUM":
        priority_level = "MEDIUM"

    coverage = overall_risk.get("coverage")
    if coverage is None:
        contributing_signals.append("Evidence coverage unavailable")
        if priority_level == "LOW":
            priority_level = "MEDIUM"
    elif coverage < 30.0:
        contributing_signals.append("Low evidence coverage")
        if priority_level == "LOW":
            priority_level = "MEDIUM"

    return {
        "level": priority_level,
        "contributing_signals": contributing_signals,
        "why_flagged": why_flagged,
        "evidence_coverage": coverage,
    }
