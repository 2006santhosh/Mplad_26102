from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from ..database import get_db
from .. import models, schemas
from ..auth_utils import get_current_user, RoleChecker
from ..official_data import get_official_project_or_404
import datetime

router = APIRouter(prefix="/api/projects/{project_id}/review", tags=["review"])

@router.post("/", response_model=schemas.ReviewLogResponse)
def add_review_log(project_id: int, review: schemas.ReviewLogCreate, db: Session = Depends(get_db), user: dict = Depends(RoleChecker(['Admin', 'State', 'District', 'Auditor']))):
    project = get_official_project_or_404(db, project_id)

    new_log = models.ReviewLog(
        project_id=project_id,
        reviewed_by=user.get("sub", "Unknown User"),
        action=review.action,
        comment=review.comment,
        created_at=datetime.datetime.utcnow()
    )
    
    # We DO NOT overwrite project.status based on an AI alert decision.
    # The review decision is an independent human overlay.
    
    db.add(new_log)
    db.commit()
    db.refresh(new_log)
    
    return new_log

@router.get("/", response_model=List[schemas.ReviewLogResponse])
def get_review_logs(project_id: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    project = get_official_project_or_404(db, project_id)

    logs = db.query(models.ReviewLog).filter(
        models.ReviewLog.project_id == project_id
    ).order_by(models.ReviewLog.created_at.desc()).all()
    
    return logs
