"""
Phase 9 — Review Cases Router
Official Investigation Workflow: Signal → Review → Case → Official Action → Audit → Resolution

Security contract:
  - READ (GET) endpoints: all authenticated users
  - WRITE (POST/PATCH) — case creation, notes, status change, assignment:
      Admin, State, District, Auditor
  - HALT action: Admin, State only (requires confirmed=True)
  - No endpoint deletes audit events or notes (append-only)

Provenance contract:
  - AI signals remain: AI ASSESSMENT
  - Government source records remain: OFFICIAL
  - Official actions on this router: OFFICIAL ACTION
  - Derived indicators remain: DERIVED

Language safety:
  - Never declare fraud confirmed, corruption proven, or AI-ordered halt.
  - AI recommends. Officials decide.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, desc
from typing import List, Optional
import datetime

from ..database import get_db
from .. import models, schemas
from ..auth_utils import get_current_user, RoleChecker
from ..models import CASE_TRANSITIONS

router = APIRouter(tags=["review-cases"])

# RBAC helpers
_reviewer_roles = ['Admin', 'State', 'District', 'Auditor']
_halt_roles = ['Admin', 'State']  # HALT requires elevated authorization

_require_reviewer = RoleChecker(_reviewer_roles)
_require_halt_auth = RoleChecker(_halt_roles)


# ─────────────────────────────────────────────────────────────────
# Utility: generate sequential case reference MPLAD-REV-XXXX
# ─────────────────────────────────────────────────────────────────

def _generate_case_reference(db: Session) -> str:
    count = db.query(models.ReviewCase).count()
    return f"MPLAD-REV-{count + 1:04d}"


def _record_audit_event(
    db: Session,
    *,
    case_id: int,
    project_id: int,
    user_id: int,
    action: str,
    previous_status: Optional[str] = None,
    new_status: Optional[str] = None,
    comment: Optional[str] = None,
    metadata_json: Optional[dict] = None,
) -> models.CaseAuditEvent:
    """Create an audit event. Caller is responsible for db.commit()."""
    event = models.CaseAuditEvent(
        case_id=case_id,
        project_id=project_id,
        user_id=user_id,
        action=action,
        previous_status=previous_status,
        new_status=new_status,
        comment=comment,
        metadata_json=metadata_json,
        provenance='OFFICIAL ACTION',
        created_at=datetime.datetime.utcnow(),
    )
    db.add(event)
    return event


# ─────────────────────────────────────────────────────────────────
# POST /api/review-cases  — Create a review case
# ─────────────────────────────────────────────────────────────────

@router.post(
    "/api/review-cases",
    response_model=schemas.ReviewCaseResponse,
    summary="Create a review case for a project (authorized officials only)",
)
def create_review_case(
    payload: schemas.ReviewCaseCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(_require_reviewer),
):
    """Explicit authorized action — AI does NOT automatically create cases.
    
    An official opens a case after reviewing AI signals.
    """
    # Verify project exists
    project = db.query(models.Project).filter(
        models.Project.id == payload.project_id
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Resolve user record
    db_user = db.query(models.User).filter(
        models.User.username == user.get("sub")
    ).first()
    if not db_user:
        raise HTTPException(status_code=401, detail="User record not found")

    # Check for existing OPEN/UNDER_REVIEW/ACTION_REQUIRED case — avoid duplicate active cases
    existing = db.query(models.ReviewCase).filter(
        models.ReviewCase.project_id == payload.project_id,
        models.ReviewCase.status.in_(["OPEN", "UNDER_REVIEW", "ACTION_REQUIRED"]),
    ).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"An active review case ({existing.case_reference}) already exists for this project. "
                   "Resolve or dismiss it before opening a new case.",
        )

    case_ref = _generate_case_reference(db)
    now = datetime.datetime.utcnow()

    case = models.ReviewCase(
        project_id=payload.project_id,
        case_reference=case_ref,
        status='OPEN',
        priority=payload.priority or 'MEDIUM',
        opened_by_id=db_user.id,
        summary=payload.summary,
        initial_note=payload.initial_note,
        triggering_signals=payload.triggering_signals or [],
        opened_at=now,
        updated_at=now,
    )
    db.add(case)
    db.flush()  # get case.id before audit event

    _record_audit_event(
        db,
        case_id=case.id,
        project_id=payload.project_id,
        user_id=db_user.id,
        action='CASE_CREATED',
        previous_status=None,
        new_status='OPEN',
        comment=payload.initial_note or "Case opened by authorized official.",
        metadata_json={"priority": case.priority, "case_reference": case_ref},
    )

    db.commit()
    db.refresh(case)

    # Eager-load relationships for response
    case = db.query(models.ReviewCase).options(
        joinedload(models.ReviewCase.opened_by),
        joinedload(models.ReviewCase.assigned_to),
        joinedload(models.ReviewCase.notes).joinedload(models.CaseNote.author),
        joinedload(models.ReviewCase.audit_events).joinedload(models.CaseAuditEvent.user),
    ).filter(models.ReviewCase.id == case.id).first()

    return case


# ─────────────────────────────────────────────────────────────────
# GET /api/review-cases  — List cases with aggregate counts
# ─────────────────────────────────────────────────────────────────

@router.get(
    "/api/review-cases",
    response_model=schemas.ReviewCaseListResponse,
    summary="List all review cases (read-only)",
)
def list_review_cases(
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    district: Optional[str] = Query(None),
    assigned_to_id: Optional[int] = Query(None),
    project_id: Optional[int] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Read-only. Returns aggregate counts alongside paginated cases.
    Uses eager loading of opened_by and assigned_to to avoid N+1.
    """
    # Aggregate counts (always across all filters except status)
    def _count(s: str) -> int:
        return db.query(func.count(models.ReviewCase.id)).filter(
            models.ReviewCase.status == s
        ).scalar() or 0

    open_count = _count('OPEN')
    under_review_count = _count('UNDER_REVIEW')
    action_required_count = _count('ACTION_REQUIRED')
    resolved_count = _count('RESOLVED')
    dismissed_count = _count('DISMISSED')

    # Build filtered query with eager load (no N+1)
    q = db.query(models.ReviewCase).options(
        joinedload(models.ReviewCase.opened_by),
        joinedload(models.ReviewCase.assigned_to),
    )

    if status:
        q = q.filter(models.ReviewCase.status == status)
    if priority:
        q = q.filter(models.ReviewCase.priority == priority)
    if assigned_to_id:
        q = q.filter(models.ReviewCase.assigned_to_id == assigned_to_id)
    if project_id:
        q = q.filter(models.ReviewCase.project_id == project_id)

    if district:
        # Join project for district filter
        q = q.join(models.Project, models.ReviewCase.project_id == models.Project.id)
        q = q.filter(models.Project.district == district)

    total = q.count()
    cases = q.order_by(desc(models.ReviewCase.opened_at)).offset(skip).limit(limit).all()

    return schemas.ReviewCaseListResponse(
        cases=cases,
        total=total,
        open_count=open_count,
        under_review_count=under_review_count,
        action_required_count=action_required_count,
        resolved_count=resolved_count,
        dismissed_count=dismissed_count,
    )


# ─────────────────────────────────────────────────────────────────
# GET /api/review-cases/{case_id}  — Full case detail
# ─────────────────────────────────────────────────────────────────

@router.get(
    "/api/review-cases/{case_id}",
    response_model=schemas.ReviewCaseResponse,
    summary="Get full review case detail with notes and audit trail (read-only)",
)
def get_review_case(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    case = db.query(models.ReviewCase).options(
        joinedload(models.ReviewCase.opened_by),
        joinedload(models.ReviewCase.assigned_to),
        joinedload(models.ReviewCase.notes).joinedload(models.CaseNote.author),
        joinedload(models.ReviewCase.audit_events).joinedload(models.CaseAuditEvent.user),
    ).filter(models.ReviewCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Review case not found")
    return case


# ─────────────────────────────────────────────────────────────────
# PATCH /api/review-cases/{case_id}  — Update status / assignment / summary
# ─────────────────────────────────────────────────────────────────

@router.patch(
    "/api/review-cases/{case_id}",
    response_model=schemas.ReviewCaseResponse,
    summary="Update case status, priority, assignment, or summary (authorized officials only)",
)
def update_review_case(
    case_id: int,
    payload: schemas.ReviewCaseUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(_require_reviewer),
):
    """Server-side validates all status transitions.
    Resolution and dismissal require resolution_note.
    """
    case = db.query(models.ReviewCase).filter(
        models.ReviewCase.id == case_id
    ).first()
    if not case:
        raise HTTPException(status_code=404, detail="Review case not found")

    db_user = db.query(models.User).filter(
        models.User.username == user.get("sub")
    ).first()
    if not db_user:
        raise HTTPException(status_code=401, detail="User record not found")

    now = datetime.datetime.utcnow()
    audit_metadata: dict = {}

    # --- Status transition ---
    if payload.status and payload.status != case.status:
        allowed_next = CASE_TRANSITIONS.get(case.status, ())
        if payload.status not in allowed_next:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid status transition: {case.status} → {payload.status}. "
                       f"Allowed: {list(allowed_next)}",
            )
        # Resolution/dismissal require a reason
        if payload.status in ('RESOLVED', 'DISMISSED'):
            if not payload.resolution_note and not case.resolution_note:
                raise HTTPException(
                    status_code=422,
                    detail=f"A resolution_note is required to {payload.status} a case.",
                )

        previous_status = case.status
        case.status = payload.status
        case.updated_at = now

        if payload.status in ('RESOLVED', 'DISMISSED'):
            case.resolved_at = now
            if payload.resolution_note:
                case.resolution_note = payload.resolution_note

        action = 'CASE_RESOLVED' if payload.status == 'RESOLVED' else (
            'CASE_DISMISSED' if payload.status == 'DISMISSED' else 'STATUS_CHANGED'
        )
        _record_audit_event(
            db,
            case_id=case.id,
            project_id=case.project_id,
            user_id=db_user.id,
            action=action,
            previous_status=previous_status,
            new_status=payload.status,
            comment=payload.resolution_note or f"Status changed to {payload.status}",
        )

    # --- Assignment ---
    if payload.assigned_to_id is not None and payload.assigned_to_id != case.assigned_to_id:
        assignee = db.query(models.User).filter(
            models.User.id == payload.assigned_to_id
        ).first()
        if not assignee:
            raise HTTPException(status_code=404, detail="Assignee user not found")
        previous_assignee_id = case.assigned_to_id
        case.assigned_to_id = payload.assigned_to_id
        case.updated_at = now
        _record_audit_event(
            db,
            case_id=case.id,
            project_id=case.project_id,
            user_id=db_user.id,
            action='CASE_ASSIGNED',
            comment=f"Case assigned to {assignee.username}",
            metadata_json={
                "assigned_to": assignee.username,
                "previous_assigned_to_id": previous_assignee_id,
            },
        )

    # --- Other simple fields ---
    if payload.priority:
        case.priority = payload.priority
        case.updated_at = now
    if payload.summary is not None:
        case.summary = payload.summary
        case.updated_at = now
    if payload.resolution_note is not None and payload.status not in ('RESOLVED', 'DISMISSED'):
        case.resolution_note = payload.resolution_note
        case.updated_at = now

    db.commit()

    # Return full case with eager loads
    case = db.query(models.ReviewCase).options(
        joinedload(models.ReviewCase.opened_by),
        joinedload(models.ReviewCase.assigned_to),
        joinedload(models.ReviewCase.notes).joinedload(models.CaseNote.author),
        joinedload(models.ReviewCase.audit_events).joinedload(models.CaseAuditEvent.user),
    ).filter(models.ReviewCase.id == case_id).first()
    return case


# ─────────────────────────────────────────────────────────────────
# POST /api/review-cases/{case_id}/notes  — Add official note
# ─────────────────────────────────────────────────────────────────

@router.post(
    "/api/review-cases/{case_id}/notes",
    response_model=schemas.CaseNoteResponse,
    summary="Add an immutable official note to a case (authorized officials only)",
)
def add_case_note(
    case_id: int,
    payload: schemas.CaseNoteCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(_require_reviewer),
):
    """Notes are append-only. No UPDATE or DELETE endpoint is provided.
    Provenance: OFFICIAL ACTION
    """
    case = db.query(models.ReviewCase).filter(
        models.ReviewCase.id == case_id
    ).first()
    if not case:
        raise HTTPException(status_code=404, detail="Review case not found")

    db_user = db.query(models.User).filter(
        models.User.username == user.get("sub")
    ).first()
    if not db_user:
        raise HTTPException(status_code=401, detail="User record not found")

    note = models.CaseNote(
        case_id=case_id,
        author_id=db_user.id,
        content=payload.content,
        provenance='OFFICIAL ACTION',
        created_at=datetime.datetime.utcnow(),
    )
    db.add(note)
    case.updated_at = datetime.datetime.utcnow()
    db.flush()

    _record_audit_event(
        db,
        case_id=case_id,
        project_id=case.project_id,
        user_id=db_user.id,
        action='NOTE_ADDED',
        comment=payload.content[:200],  # truncated for audit readability
    )

    db.commit()
    db.refresh(note)

    # Load author relationship
    note = db.query(models.CaseNote).options(
        joinedload(models.CaseNote.author)
    ).filter(models.CaseNote.id == note.id).first()

    return note


# ─────────────────────────────────────────────────────────────────
# POST /api/review-cases/{case_id}/actions  — Official action
# ─────────────────────────────────────────────────────────────────

@router.post(
    "/api/review-cases/{case_id}/actions",
    response_model=schemas.CaseAuditEventResponse,
    summary="Record an official action on a case: COMMENT / FLAG / CLEAR / HALT",
)
def add_case_action(
    case_id: int,
    payload: schemas.CaseActionRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(_require_reviewer),
):
    """Official actions on a case.

    COMMENT: Record an official observation.
    FLAG: Mark the case for further review.
    CLEAR: Official indicates current signals do not require continued review.
    HALT: Authorized official records that a halt/action has been ordered.

    CRITICAL: HALT is NEVER triggered automatically by AI.
    HALT requires:
      - An authorized official (Admin or State role)
      - confirmed=True in the request body
      - A non-empty reason/comment
    """
    case = db.query(models.ReviewCase).filter(
        models.ReviewCase.id == case_id
    ).first()
    if not case:
        raise HTTPException(status_code=404, detail="Review case not found")

    db_user = db.query(models.User).filter(
        models.User.username == user.get("sub")
    ).first()
    if not db_user:
        raise HTTPException(status_code=401, detail="User record not found")

    # HALT requires elevated authorization
    if payload.action == 'HALT':
        if db_user.role not in _halt_roles:
            raise HTTPException(
                status_code=403,
                detail="HALT is an authorized official action and requires Admin or State role. "
                       "Insufficient authorization.",
            )
        if not payload.confirmed:
            raise HTTPException(
                status_code=422,
                detail="HALT requires explicit confirmation (confirmed=true) and an authorized official. "
                       "AI cannot trigger HALT automatically.",
            )

    action_map = {
        'COMMENT': 'COMMENT_RECORDED',
        'FLAG': 'FLAG_RECORDED',
        'CLEAR': 'CLEAR_RECORDED',
        'HALT': 'HALT_RECORDED',
    }
    audit_action = action_map[payload.action]

    event = _record_audit_event(
        db,
        case_id=case_id,
        project_id=case.project_id,
        user_id=db_user.id,
        action=audit_action,
        comment=payload.comment,
        metadata_json={
            "action_type": payload.action,
            "confirmed": payload.confirmed if payload.action == 'HALT' else None,
        },
    )
    case.updated_at = datetime.datetime.utcnow()
    db.commit()

    event = db.query(models.CaseAuditEvent).options(
        joinedload(models.CaseAuditEvent.user)
    ).filter(models.CaseAuditEvent.id == event.id).first()

    return event


# ─────────────────────────────────────────────────────────────────
# GET /api/review-cases/{case_id}/audit  — Audit trail
# ─────────────────────────────────────────────────────────────────

@router.get(
    "/api/review-cases/{case_id}/audit",
    response_model=List[schemas.CaseAuditEventResponse],
    summary="Get the append-only audit trail for a case (read-only)",
)
def get_case_audit(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Read-only. Audit events are never deleted.
    Every event shows: WHO (user), WHAT (action), WHEN (created_at).
    """
    case = db.query(models.ReviewCase).filter(
        models.ReviewCase.id == case_id
    ).first()
    if not case:
        raise HTTPException(status_code=404, detail="Review case not found")

    events = db.query(models.CaseAuditEvent).options(
        joinedload(models.CaseAuditEvent.user)
    ).filter(
        models.CaseAuditEvent.case_id == case_id
    ).order_by(models.CaseAuditEvent.created_at.asc()).all()

    return events


# ─────────────────────────────────────────────────────────────────
# GET /api/projects/{project_id}/review-cases  — Cases for a project
# ─────────────────────────────────────────────────────────────────

@router.get(
    "/api/projects/{project_id}/review-cases",
    response_model=List[schemas.ReviewCaseSummary],
    summary="Get all review cases for a specific project (read-only)",
)
def get_project_review_cases(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    project = db.query(models.Project).filter(
        models.Project.id == project_id
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    cases = db.query(models.ReviewCase).options(
        joinedload(models.ReviewCase.opened_by),
        joinedload(models.ReviewCase.assigned_to),
    ).filter(
        models.ReviewCase.project_id == project_id
    ).order_by(desc(models.ReviewCase.opened_at)).all()

    return cases
