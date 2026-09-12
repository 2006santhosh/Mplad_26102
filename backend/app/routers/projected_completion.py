from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models, schemas
from ..auth_utils import get_current_user
from ..official_data import get_official_project_or_404
import datetime
import math

router = APIRouter(prefix="/api/projected-completion", tags=["projected-completion"])

def create_unknown(project_id: int, message: str) -> schemas.ProjectedCompletionRiskResponse:
    return schemas.ProjectedCompletionRiskResponse(
        project_id=project_id,
        risk_score=0,
        risk_level="UNKNOWN",
        explanation=message,
        source_type="Projected Completion Engine"
    )

@router.get("/{project_id}", response_model=schemas.ProjectedCompletionRiskResponse)
def get_projected_completion_risk(project_id: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    p = get_official_project_or_404(db, project_id)

    if p.status == "COMPLETED":
        return schemas.ProjectedCompletionRiskResponse(
            project_id=project_id,
            risk_score=0,
            risk_level="LOW",
            explanation="Project is already completed.",
            source_type="Projected Completion Engine",
            planned_date=p.planned_completion,
            projected_date=p.actual_completion or datetime.date.today(),
            delay_days=0
        )

    if not p.planned_start or not p.planned_completion:
        return create_unknown(project_id, "Planned start or completion date is missing.")

    planned_duration = (p.planned_completion - p.planned_start).days
    if planned_duration < 0:
        return create_unknown(project_id, "Invalid dates: planned completion is before planned start.")

    # Get valid progress history
    reports = db.query(models.ProjectProgress).filter(
        models.ProjectProgress.project_id == project_id,
        models.ProjectProgress.percentage != None,
        models.ProjectProgress.reported_at != None,
        models.ProjectProgress.percentage >= 0,
        models.ProjectProgress.percentage <= 100
    ).order_by(models.ProjectProgress.reported_at.asc()).all()

    if len(reports) < 2:
        return create_unknown(project_id, "Insufficient progress history to estimate completion.")

    latest = reports[-1]
    current_progress = float(latest.percentage)
    latest_date = latest.reported_at.date() if isinstance(latest.reported_at, datetime.datetime) else latest.reported_at

    # Find the earliest report to calculate a stable historical velocity
    earliest = reports[0]
    earliest_progress = float(earliest.percentage)
    earliest_date = earliest.reported_at.date() if isinstance(earliest.reported_at, datetime.datetime) else earliest.reported_at

    elapsed_days = (latest_date - earliest_date).days
    
    if elapsed_days <= 0:
        return create_unknown(project_id, "Insufficient elapsed time between progress observations to calculate velocity.")

    progress_diff = current_progress - earliest_progress
    velocity = progress_diff / elapsed_days

    remaining_progress = 100.0 - current_progress

    if remaining_progress <= 0:
        return schemas.ProjectedCompletionRiskResponse(
            project_id=project_id,
            risk_score=0,
            risk_level="LOW",
            explanation="Project is effectively complete based on progress history.",
            source_type="Projected Completion Engine",
            planned_date=p.planned_completion,
            projected_date=latest_date,
            velocity=velocity,
            delay_days=0
        )

    if velocity <= 0:
        return schemas.ProjectedCompletionRiskResponse(
            project_id=project_id,
            risk_score=90,
            risk_level="HIGH",
            explanation="Analytical Progress Proxy is stalled or non-positive. High risk of severe delay.",
            source_type="Projected Completion Engine",
            planned_date=p.planned_completion,
            velocity=velocity
        )

    projected_remaining_days = remaining_progress / velocity
    projected_date = latest_date + datetime.timedelta(days=int(math.ceil(projected_remaining_days)))
    
    projected_delay_days = max(0, (projected_date - p.planned_completion).days)
    
    delay_ratio = projected_delay_days / (planned_duration if planned_duration > 0 else 1)

    if delay_ratio > 0.5:
        risk_level = "HIGH"
        risk_score = 80
    elif delay_ratio > 0.2:
        risk_level = "MEDIUM"
        risk_score = 50
    else:
        risk_level = "LOW"
        risk_score = 20
        
    explanation = "Project is on track to complete on time." if projected_delay_days == 0 else f"Projected completion is delayed by {projected_delay_days} days."

    return schemas.ProjectedCompletionRiskResponse(
        project_id=project_id,
        risk_score=risk_score,
        risk_level=risk_level,
        explanation=explanation,
        source_type="Projected Completion Engine",
        projected_date=projected_date,
        planned_date=p.planned_completion,
        velocity=velocity,
        delay_days=projected_delay_days
    )
