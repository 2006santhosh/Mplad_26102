from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from ..database import get_db
from .. import models, schemas
from ..auth_utils import get_current_user
import datetime

router = APIRouter(prefix="/api/projects/{project_id}/decision-support", tags=["decision-support"])

@router.get("", response_model=schemas.DecisionSupportResponse)
@router.get("/", response_model=schemas.DecisionSupportResponse)
def get_decision_support(project_id: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    p = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")

    # 1. Fetch all required existing data in a read-only manner
    risk_assessment = db.query(models.RiskAssessment).filter(models.RiskAssessment.project_id == project_id).order_by(desc(models.RiskAssessment.created_at)).first()
    compliance = db.query(models.ComplianceAssessment).filter(models.ComplianceAssessment.project_id == project_id).order_by(desc(models.ComplianceAssessment.assessed_at)).first()
    early_warnings = db.query(models.EarlyWarning).filter(models.EarlyWarning.project_id == project_id).order_by(desc(models.EarlyWarning.detected_at)).all()
    predictive = db.query(models.PredictiveCompletionAssessment).filter(models.PredictiveCompletionAssessment.project_id == project_id).order_by(desc(models.PredictiveCompletionAssessment.created_at)).first()
    
    # 2. Risk Trend analysis (from history)
    history = db.query(models.RiskHistory).filter(models.RiskHistory.project_id == project_id).order_by(models.RiskHistory.recorded_at.asc()).all()
    risk_trend = {"trend": "STABLE", "explanation": "Risk levels have remained stable."}
    if len(history) > 1:
        first_score = history[0].risk_score
        last_score = history[-1].risk_score
        if first_score is not None and last_score is not None:
            if last_score > first_score + 10:
                risk_trend = {"trend": "INCREASING", "explanation": "Risk has increased significantly over time."}
            elif last_score < first_score - 10:
                risk_trend = {"trend": "DECREASING", "explanation": "Risk has decreased over time."}
    elif len(history) == 0:
        risk_trend = {"trend": "INSUFFICIENT_HISTORY", "explanation": "Not enough history to determine trend."}

    # 3. Overall Risk Dictionary
    overall_risk = {
        "level": risk_assessment.overall_risk_level if risk_assessment else "LIMITED",
        "score": risk_assessment.score if risk_assessment else None,
        "coverage": risk_assessment.assessment_coverage_pct if risk_assessment else 0.0
    }

    # 4. Compliance Dictionary
    compliance_dict = {
        "status": compliance.overall_status if compliance else "NOT_ASSESSABLE",
        "coverage": compliance.coverage_percentage if compliance else 0.0,
        "pass_count": compliance.pass_count if compliance else 0,
        "fail_count": compliance.fail_count if compliance else 0,
        "review_count": compliance.review_count if compliance else 0,
    }

    # 5. Early Warnings
    open_warnings = [w for w in early_warnings if w.status in ["OPEN", "ACKNOWLEDGED", "UNDER_REVIEW"]]
    warnings_list = [
        {
            "id": w.id,
            "type": w.warning_type,
            "level": w.warning_level,
            "status": w.status,
            "explanation": w.explanation,
            "provenance": w.provenance
        }
        for w in open_warnings
    ]

    # 6. Completion Risk Dictionary
    completion_risk_dict = {
        "level": predictive.risk_level if predictive and predictive.risk_level else "UNKNOWN",
        "score": predictive.risk_score if predictive else None,
        "confidence": predictive.confidence if predictive else "LOW",
        "drivers": predictive.drivers if predictive and predictive.drivers else []
    }

    # 7. Data Quality Scorecard
    progress = db.query(models.ProjectProgress).filter(models.ProjectProgress.project_id == project_id).first()
    financials = db.query(models.ProjectFinancials).filter(models.ProjectFinancials.project_id == project_id).first()
    
    data_quality = schemas.DataQuality(
        gps_coverage="AVAILABLE" if p.latitude and p.longitude else "UNAVAILABLE",
        analytical_progress_coverage="AVAILABLE" if progress else "UNAVAILABLE",
        financial_data_coverage="AVAILABLE" if financials else "UNAVAILABLE",
        contractor_information_coverage="UNAVAILABLE", # simplified for now
        risk_history_coverage="AVAILABLE" if len(history) > 0 else "UNAVAILABLE",
        compliance_coverage="AVAILABLE" if compliance else "UNAVAILABLE"
    )

    # 8. Flag Reasons and Review Priority
    why_flagged = []
    contributing_signals = []
    priority_level = "LOW"
    
    if overall_risk["level"] in ["HIGH", "CRITICAL"]:
        priority_level = "HIGH" if overall_risk["level"] == "HIGH" else "CRITICAL"
        contributing_signals.append(f"{overall_risk['level']} current risk")
        why_flagged.append(schemas.FlagReason(
            signal_type="Current Risk",
            severity=overall_risk["level"],
            explanation="The project currently exhibits elevated risk factors.",
            evidence={"score": overall_risk["score"]},
            provenance="AI ASSESSMENT"
        ))

    if risk_trend["trend"] == "INCREASING":
        if priority_level in ["LOW", "MEDIUM"]: priority_level = "HIGH"
        contributing_signals.append("INCREASING risk trend")
        why_flagged.append(schemas.FlagReason(
            signal_type="Risk Trend",
            severity="HIGH",
            explanation=risk_trend["explanation"],
            evidence={"trend": "INCREASING"},
            provenance="AI ASSESSMENT"
        ))

    if compliance_dict["status"] in ["FAIL", "REVIEW"]:
        if priority_level in ["LOW", "MEDIUM"]: priority_level = "HIGH"
        contributing_signals.append(f"Compliance {compliance_dict['status']}")
        why_flagged.append(schemas.FlagReason(
            signal_type="Compliance",
            severity="HIGH" if compliance_dict["status"] == "FAIL" else "MEDIUM",
            explanation="Compliance checks have flagged potential issues.",
            evidence={"fails": compliance_dict["fail_count"], "reviews": compliance_dict["review_count"]},
            provenance="AI ASSESSMENT"
        ))

    if len(open_warnings) > 0:
        if any(w.warning_level == "CRITICAL" for w in open_warnings):
            priority_level = "CRITICAL"
        elif priority_level in ["LOW", "MEDIUM"]:
            priority_level = "HIGH"
        
        contributing_signals.append(f"{len(open_warnings)} open early warnings")
        for w in open_warnings:
            if w.warning_level in ["HIGH", "CRITICAL"]:
                why_flagged.append(schemas.FlagReason(
                    signal_type="Early Warning",
                    severity=w.warning_level,
                    explanation=w.explanation,
                    evidence={"type": w.warning_type},
                    provenance=w.provenance
                ))

    if completion_risk_dict["level"] in ["HIGH", "CRITICAL"]:
        if priority_level in ["LOW", "MEDIUM"]: priority_level = "HIGH"
        contributing_signals.append(f"{completion_risk_dict['level']} completion risk")
        why_flagged.append(schemas.FlagReason(
            signal_type="Predictive Completion",
            severity=completion_risk_dict["level"],
            explanation="Predictive assessment indicates a risk of non-completion or delay.",
            evidence={"confidence": completion_risk_dict["confidence"]},
            provenance="AI ASSESSMENT"
        ))

    if priority_level == "LOW" and overall_risk["level"] == "MEDIUM":
        priority_level = "MEDIUM"

    _coverage = overall_risk["coverage"]
    if _coverage is not None and _coverage < 30.0:
        contributing_signals.append("Low evidence coverage")
        if priority_level == "LOW":
            priority_level = "MEDIUM" # elevate slightly due to uncertainty

    review_priority = schemas.ReviewPriority(
        level=priority_level,
        contributing_signals=contributing_signals,
        why_flagged=why_flagged,
        evidence_coverage=overall_risk["coverage"]
    )

    # 9. Timeline
    timeline_events = []
    
    if p.planned_start:
        timeline_events.append(schemas.TimelineEvent(
            date=p.planned_start,
            event_type="Sanction recorded",
            description=f"Project sanctioned with amount ₹{p.sanctioned_amount}",
            provenance="OFFICIAL"
        ))
    
    if progress:
        timeline_events.append(schemas.TimelineEvent(
            date=progress.reported_at.date() if isinstance(progress.reported_at, datetime.datetime) else progress.reported_at,
            event_type="Progress Update",
            description=f"Analytical Progress Proxy updated to {progress.percentage}%",
            provenance="DERIVED"
        ))
        
    for h in history:
        timeline_events.append(schemas.TimelineEvent(
            date=h.recorded_at.date() if isinstance(h.recorded_at, datetime.datetime) else h.recorded_at,
            event_type="Risk Assessment",
            description=f"Risk level assessed as {h.risk_level}",
            provenance="AI ASSESSMENT"
        ))
        
    if compliance:
        timeline_events.append(schemas.TimelineEvent(
            date=compliance.assessed_at.date() if isinstance(compliance.assessed_at, datetime.datetime) else compliance.assessed_at,
            event_type="Compliance Assessment",
            description=f"Compliance status assessed as {compliance.overall_status}",
            provenance="AI ASSESSMENT"
        ))
        
    for w in early_warnings:
        timeline_events.append(schemas.TimelineEvent(
            date=w.detected_at.date() if isinstance(w.detected_at, datetime.datetime) else w.detected_at,
            event_type="Early Warning",
            description=f"Warning triggered: {w.title}",
            provenance="AI ASSESSMENT"
        ))

    # Sort timeline by date desc
    timeline_events.sort(key=lambda x: x.date, reverse=True)

    # 10. Provenance
    provenance = {
        "sanction_amount": "OFFICIAL",
        "work_stage": "OFFICIAL",
        "analytical_progress": "DERIVED",
        "risk_score": "AI ASSESSMENT",
        "early_warnings": "AI ASSESSMENT",
        "completion_risk": "AI ASSESSMENT"
    }

    return schemas.DecisionSupportResponse(
        project_id=project_id,
        overall_risk=overall_risk,
        risk_trend=risk_trend,
        compliance=compliance_dict,
        early_warnings=warnings_list,
        completion_risk=completion_risk_dict,
        review_priority=review_priority,
        data_quality=data_quality,
        timeline=timeline_events,
        provenance=provenance
    )
