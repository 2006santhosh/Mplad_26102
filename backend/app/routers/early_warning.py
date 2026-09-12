from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models, schemas
from ..auth_utils import get_current_user, RoleChecker
from ..risk_engine.early_warning import EarlyWarningEngine
from ..official_data import get_official_project_or_404

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
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    READ-ONLY: returns persisted early warnings for a project.
    Does NOT run the assessment engine.
    Does NOT insert, update, or delete any records.
    Use POST /early-warnings/assess to trigger the engine.
    """
    p = get_official_project_or_404(db, project_id)

    warnings = (
        db.query(models.EarlyWarning)
        .filter(models.EarlyWarning.project_id == project_id)
        .order_by(models.EarlyWarning.detected_at.desc())
        .limit(limit)
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
    p = get_official_project_or_404(db, project_id)

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

@router.patch("/{project_id}/early-warning/{warning_id}", response_model=schemas.EarlyWarningItem)
def update_warning_status(project_id: int, warning_id: int, payload: schemas.WarningStatusUpdate,
                          db: Session = Depends(get_db), user: dict = Depends(RoleChecker(["Admin", "Auditor", "State", "District"]))):
    get_official_project_or_404(db, project_id)
    warning = db.query(models.EarlyWarning).filter(
        models.EarlyWarning.id == warning_id,
        models.EarlyWarning.project_id == project_id,
    ).first()
    if not warning:
        raise HTTPException(status_code=404, detail="Early warning not found")
    allowed = {
        "OPEN": {"ACKNOWLEDGED", "UNDER_REVIEW", "DISMISSED"},
        "ACKNOWLEDGED": {"UNDER_REVIEW", "RESOLVED", "DISMISSED"},
        "UNDER_REVIEW": {"RESOLVED", "DISMISSED"},
        "RESOLVED": set(),
        "DISMISSED": set(),
    }
    if payload.status not in allowed.get(warning.status, set()):
        raise HTTPException(status_code=422, detail=f"Invalid warning transition: {warning.status} -> {payload.status}")
    official_user = db.query(models.User).filter(models.User.username == user.get('sub')).first()
    if official_user:
        db.add(models.AuditLog(
            user_id=official_user.id,
            action='EARLY_WARNING_STATUS_CHANGED',
            entity_type='EarlyWarning',
            entity_id=warning.id,
            details=f'{warning.status} -> {payload.status}; project_id={project_id}',
        ))
    warning.status = payload.status
    db.commit()
    db.refresh(warning)
    return _serialize_warnings([warning])[0]
