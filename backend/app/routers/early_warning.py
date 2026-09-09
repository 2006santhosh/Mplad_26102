from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models, schemas
from ..auth_utils import get_current_user, RoleChecker
from ..risk_engine.early_warning import EarlyWarningEngine

router = APIRouter(prefix="/api/projects", tags=["early-warnings"])

# Active warning statuses — count these as "live" warnings
ACTIVE_STATUSES = ("OPEN", "ACKNOWLEDGED", "UNDER_REVIEW")


def _serialize_warnings(warnings):
    return [
        {
            "id": w.id,
            "warning_type": w.warning_type,
            "warning_level": w.warning_level,
            "status": w.status,
            "title": w.title,
            "explanation": w.explanation,
            "trigger_signature": w.trigger_signature,
            "evidence": w.evidence,
            "provenance": w.provenance,
            "assessment_coverage": w.assessment_coverage,
            "confidence": w.confidence,
            "detected_at": w.detected_at,
            "engine_version": w.engine_version,
        }
        for w in warnings
    ]


@router.get("/{project_id}/early-warning", response_model=schemas.EarlyWarningResponse)
def get_project_warnings(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    READ-ONLY: returns persisted early warnings for a project.
    Does NOT run the assessment engine.
    Does NOT insert, update, or delete any records.
    Use POST /early-warnings/assess to trigger the engine.
    """
    p = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")

    warnings = (
        db.query(models.EarlyWarning)
        .filter(models.EarlyWarning.project_id == project_id)
        .order_by(models.EarlyWarning.detected_at.desc())
        .all()
    )
    return schemas.EarlyWarningResponse(
        project_id=project_id,
        warnings=_serialize_warnings(warnings),
        source_type="Early Warning Engine",
    )


@router.post("/{project_id}/early-warnings/assess", response_model=schemas.EarlyWarningResponse)
def assess_project_warnings(
    project_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(RoleChecker(["Admin", "Auditor", "State", "District"])),
):
    """
    MUTATING: runs the EarlyWarningEngine for this project, persists new warnings
    (deduplication via trigger_signature), and returns all current warnings.
    """
    p = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")

    engine = EarlyWarningEngine(db)
    engine.assess_project(project_id)

    warnings = (
        db.query(models.EarlyWarning)
        .filter(models.EarlyWarning.project_id == project_id)
        .order_by(models.EarlyWarning.detected_at.desc())
        .all()
    )
    return schemas.EarlyWarningResponse(
        project_id=project_id,
        warnings=_serialize_warnings(warnings),
        source_type="Early Warning Engine",
    )
