from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models, schemas
from ..auth_utils import get_current_user
import datetime

router = APIRouter(prefix="/api/projects/{project_id}/early-warning", tags=["early_warning"])

@router.get("/", response_model=schemas.EarlyWarningResponse)
def get_early_warnings(project_id: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    p = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")

    warnings = []
    
    # Get latest progress and financials
    prog = db.query(models.ProjectProgress).filter(
        models.ProjectProgress.project_id == project_id
    ).order_by(models.ProjectProgress.reported_at.desc()).first()
    
    fin = db.query(models.ProjectFinancials).filter(
        models.ProjectFinancials.project_id == project_id
    ).order_by(models.ProjectFinancials.updated_at.desc()).first()
    
    progress_pct = prog.percentage if prog and prog.percentage is not None else None
    expenditure = float(fin.expenditure) if fin and fin.expenditure is not None else None
    sanctioned = float(p.sanctioned_amount) if p.sanctioned_amount is not None else None

    # Validate data and generate anomaly warnings
    valid_progress = False
    valid_expenditure = False
    
    if progress_pct is not None:
        if 0 <= progress_pct <= 100:
            valid_progress = True
        else:
            warnings.append(schemas.EarlyWarningItem(
                type="Data Anomaly",
                severity="LOW",
                message=f"Invalid physical progress recorded ({progress_pct}%)."
            ))
            
    if expenditure is not None:
        if expenditure >= 0:
            valid_expenditure = True
        else:
            warnings.append(schemas.EarlyWarningItem(
                type="Data Anomaly",
                severity="LOW",
                message=f"Invalid negative expenditure recorded (₹{expenditure})."
            ))

    # Check 1: Burn Rate Risk (mutually exclusive)
    if valid_progress and valid_expenditure and sanctioned is not None and sanctioned > 0:
        burn_rate = expenditure / sanctioned
        
        if burn_rate > 0.8 and progress_pct < 50:
            warnings.append(schemas.EarlyWarningItem(
                type="Burn Rate",
                severity="HIGH",
                message=f"High fund consumption ({burn_rate*100:.1f}%) with low physical progress ({progress_pct}%)."
            ))
        elif burn_rate > 0.9 and progress_pct >= 50 and progress_pct < 80:
            warnings.append(schemas.EarlyWarningItem(
                type="Burn Rate",
                severity="MEDIUM",
                message=f"Funds nearly exhausted ({burn_rate*100:.1f}%) while project is incomplete ({progress_pct}%)."
            ))

    # Check 2: Deadline Risk
    if p.status == "ONGOING" and p.planned_completion:
        today = datetime.date.today()
        days_remaining = (p.planned_completion - today).days
        
        if days_remaining < 0:
            warnings.append(schemas.EarlyWarningItem(
                type="Deadline",
                severity="HIGH",
                message=f"Project is overdue by {abs(days_remaining)} days."
            ))
        elif days_remaining <= 90:
            if valid_progress and progress_pct < 70:
                warnings.append(schemas.EarlyWarningItem(
                    type="Deadline",
                    severity="MEDIUM",
                    message=f"Deadline approaching in {days_remaining} days, but progress is only {progress_pct}%."
                ))

    # Check 3: Stalled Project
    if p.status == "ONGOING":
        if prog and prog.reported_at and valid_progress and progress_pct < 100:
            days_since_update = (datetime.date.today() - prog.reported_at.date()).days
            if days_since_update > 180:
                warnings.append(schemas.EarlyWarningItem(
                    type="Stagnation",
                    severity="MEDIUM",
                    message=f"No progress updates recorded in over 6 months. Project may be stalled."
                ))

    return schemas.EarlyWarningResponse(
        project_id=project_id,
        warnings=warnings,
        source_type="Early Warning Engine"
    )
