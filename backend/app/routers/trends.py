from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models, schemas
from ..auth_utils import get_current_user
import datetime

router = APIRouter(prefix="/api/trends", tags=["trends"])

@router.get("/{project_id}", response_model=list[schemas.TrendResponse])
def get_project_trends(project_id: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    p = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")

    responses = []

    # 1. Financial Trends (Expenditure)
    financials = db.query(models.ProjectFinancials).filter(
        models.ProjectFinancials.project_id == project_id
    ).order_by(models.ProjectFinancials.updated_at.asc()).all()
    
    fin_data = []
    for f in financials:
        val = f.expenditure
        if val is None:
            continue
        
        is_invalid = False
        note = None
        if val < 0:
            is_invalid = True
            note = "Invalid Negative Expenditure"
            
        fin_data.append(schemas.TrendDataPoint(
            date=f.updated_at.date() if f.updated_at else datetime.date.today(),
            value=float(val),
            is_invalid=is_invalid,
            note=note
        ))
    if fin_data:
        responses.append(schemas.TrendResponse(
            type="expenditure",
            data=fin_data,
            source_type="Financial Logs"
        ))

    # 2. Progress Trends
    progress = db.query(models.ProjectProgress).filter(
        models.ProjectProgress.project_id == project_id
    ).order_by(models.ProjectProgress.reported_at.asc()).all()
    
    prog_data = []
    for pr in progress:
        val = pr.percentage
        if val is None:
            continue
            
        is_invalid = False
        note = None
        if val < 0 or val > 100:
            is_invalid = True
            note = f"Invalid Progress ({val}%)"
            
        prog_data.append(schemas.TrendDataPoint(
            date=pr.reported_at.date() if pr.reported_at else datetime.date.today(),
            value=float(val),
            is_invalid=is_invalid,
            note=note
        ))
    if prog_data:
        responses.append(schemas.TrendResponse(
            type="progress",
            data=prog_data,
            source_type="Progress Reports"
        ))
        
    return responses
