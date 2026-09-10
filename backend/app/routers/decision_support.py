from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from ..database import get_db
from .. import models, schemas
from ..auth_utils import get_current_user
from ..services.review_priority import calculate_review_priority
import datetime

router = APIRouter(prefix="/api/projects/{project_id}/decision-support", tags=["decision-support"])

@router.get("", response_model=schemas.DecisionSupportResponse)
@router.get("/", response_model=schemas.DecisionSupportResponse)
def get_decision_support(project_id: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    p = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")

    # 1. Fetch all required existing data in a read-only manner
    risk_assessment = db.query(models.RiskAssessment).filter(models.RiskAssessment.project_id == project_id).order_by(desc(models.RiskAssessment.created_at), desc(models.RiskAssessment.id)).first()
    compliance = db.query(models.ComplianceAssessment).filter(models.ComplianceAssessment.project_id == project_id).order_by(desc(models.ComplianceAssessment.assessed_at), desc(models.ComplianceAssessment.id)).first()
    early_warnings = db.query(models.EarlyWarning).filter(models.EarlyWarning.project_id == project_id).order_by(desc(models.EarlyWarning.detected_at), desc(models.EarlyWarning.id)).limit(100).all()
    predictive = db.query(models.PredictiveCompletionAssessment).filter(models.PredictiveCompletionAssessment.project_id == project_id).order_by(desc(models.PredictiveCompletionAssessment.created_at), desc(models.PredictiveCompletionAssessment.id)).first()
    
    # 2. Risk Trend analysis (from history)
    history = db.query(models.RiskHistory).filter(models.RiskHistory.project_id == project_id).order_by(desc(models.RiskHistory.recorded_at), desc(models.RiskHistory.id)).limit(100).all()
    history.reverse()
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
        "coverage": risk_assessment.assessment_coverage_pct if risk_assessment else None
    }

    # 4. Compliance Dictionary
    compliance_dict = {
        "status": compliance.overall_status if compliance else "NOT_ASSESSABLE",
        "coverage": compliance.coverage_percentage if compliance else None,
        "pass_count": compliance.pass_count if compliance else None,
        "fail_count": compliance.fail_count if compliance else None,
        "review_count": compliance.review_count if compliance else None,
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
        "confidence": predictive.confidence if predictive else None,
        "drivers": predictive.drivers if predictive and predictive.drivers else []
    }

    # 7. Data Quality Scorecard
    progress = db.query(models.ProjectProgress).filter(models.ProjectProgress.project_id == project_id).order_by(desc(models.ProjectProgress.reported_at), desc(models.ProjectProgress.id)).first()
    financials = db.query(models.ProjectFinancials).filter(models.ProjectFinancials.project_id == project_id).order_by(desc(models.ProjectFinancials.updated_at), desc(models.ProjectFinancials.id)).first()
    
    data_quality = schemas.DataQuality(
        gps_coverage="AVAILABLE" if p.latitude is not None and p.longitude is not None else "UNAVAILABLE",
        analytical_progress_coverage="AVAILABLE" if progress else "UNAVAILABLE",
        financial_data_coverage="AVAILABLE" if financials else "UNAVAILABLE",
        contractor_information_coverage="UNAVAILABLE", # simplified for now
        risk_history_coverage="AVAILABLE" if len(history) > 0 else "UNAVAILABLE",
        compliance_coverage="AVAILABLE" if compliance else "UNAVAILABLE"
    )

    # 8. Flag Reasons and Review Priority
    priority = calculate_review_priority(
        overall_risk=overall_risk,
        risk_trend=risk_trend,
        compliance=compliance_dict,
        open_warnings=open_warnings,
        completion_risk=completion_risk_dict,
    )
    review_priority = schemas.ReviewPriority(
        level=priority["level"],
        contributing_signals=priority["contributing_signals"],
        why_flagged=[schemas.FlagReason(**flag) for flag in priority["why_flagged"]],
        evidence_coverage=priority["evidence_coverage"],
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
    source_type = p.data_source.source_type if p.data_source else "UNAVAILABLE"
    source_provenance = source_type if source_type in ["OFFICIAL", "SYNTHETIC"] else "UNAVAILABLE"
    provenance = {
        "sanction_amount": source_provenance if p.sanctioned_amount is not None else "UNAVAILABLE",
        "work_stage": source_provenance if p.work_stage else "UNAVAILABLE",
        "analytical_progress": "DERIVED" if progress and source_type == "OFFICIAL" else ("SYNTHETIC" if progress else "UNAVAILABLE"),
        "risk_score": "AI ASSESSMENT" if risk_assessment else "UNAVAILABLE",
        "early_warnings": "AI ASSESSMENT" if early_warnings else "UNAVAILABLE",
        "completion_risk": "AI ASSESSMENT" if predictive else "UNAVAILABLE",
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
