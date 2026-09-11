from sqlalchemy import Column, Integer, String, Numeric, Date, DateTime, ForeignKey, Text, Float, JSON, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base
import datetime

class DataSource(Base):
    __tablename__ = "data_sources"
    id = Column(Integer, primary_key=True, index=True)
    source_name = Column(String, nullable=False)
    source_type = Column(String, nullable=False) # OFFICIAL, DERIVED, SYNTHETIC, EXTERNAL
    source_url = Column(String, nullable=True)
    dataset_version = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    last_updated = Column(DateTime, server_default=func.now())

    mps = relationship("MP", back_populates="data_source")
    projects = relationship("Project", back_populates="data_source")

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    role = Column(String, nullable=False) # Admin, State, District, MP, Auditor
    password_hash = Column(String, nullable=False)

class MP(Base):
    __tablename__ = "mps"
    id = Column(Integer, primary_key=True, index=True)
    data_source_id = Column(Integer, ForeignKey("data_sources.id"), nullable=False)
    name = Column(String, nullable=False)
    state = Column(String, nullable=False)
    status = Column(String, nullable=True) # Elected/Nominated
    tenure = Column(String, nullable=True)
    allocated_amount = Column(Numeric(15, 2), nullable=True)
    constituency = Column(String, nullable=True)
    
    data_source = relationship("DataSource", back_populates="mps")
    projects = relationship("Project", back_populates="mp")

class Project(Base):
    __tablename__ = "projects"
    id = Column(Integer, primary_key=True, index=True)
    mp_id = Column(Integer, ForeignKey("mps.id"), nullable=False)
    data_source_id = Column(Integer, ForeignKey("data_sources.id"), nullable=False)
    work_id = Column(String, nullable=True, index=True)
    work_stage = Column(String, nullable=True)
    district = Column(String, nullable=True)
    constituency = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    work_category = Column(String, nullable=True)
    category = Column(String, index=True)
    sanctioned_amount = Column(Numeric(15, 2))
    location = Column(String)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    gps_provenance = Column(String, nullable=False, server_default="UNAVAILABLE")
    planned_start = Column(Date, nullable=True)
    planned_completion = Column(Date, nullable=True)
    actual_completion = Column(Date, nullable=True)
    status = Column(String, index=True)

    mp = relationship("MP", back_populates="projects")
    data_source = relationship("DataSource", back_populates="projects")
    financials = relationship("ProjectFinancials", back_populates="project")
    progress = relationship("ProjectProgress", back_populates="project")
    contractors = relationship("ProjectContractor", back_populates="project")
    risk_assessments = relationship("RiskAssessment", back_populates="project")
    risk_history = relationship("RiskHistory", back_populates="project")
    review_logs = relationship("ReviewLog", back_populates="project")
    reviews = relationship("Review", back_populates="project")
    compliance_assessments = relationship("ComplianceAssessment", back_populates="project")
    early_warnings = relationship("EarlyWarning", back_populates="project")
    predictive_completion_assessments = relationship("PredictiveCompletionAssessment", back_populates="project")
    review_cases = relationship("ReviewCase", back_populates="project")

    @property
    def source_type(self):
        return self.data_source.source_type if self.data_source else None

    @property
    def provenance(self):
        has_expenditure = len([f for f in self.financials if f.expenditure is not None and float(f.expenditure) > 0]) > 0
        has_progress = len([p for p in self.progress if p.percentage is not None]) > 0
        
        stype = self.source_type
        base = "SYNTHETIC" if stype == "SYNTHETIC" else "OFFICIAL"
        
        return {
            "sanctioned_amount": base if self.sanctioned_amount is not None else "UNAVAILABLE",
            "work_stage": base if self.work_stage else "UNAVAILABLE",
            "latitude": base if self.latitude is not None else "UNAVAILABLE",
            "longitude": base if self.longitude is not None else "UNAVAILABLE",
            "expenditure": base if has_expenditure else "UNAVAILABLE",
            "physical_progress": "DERIVED" if has_progress and stype != "SYNTHETIC" else ("SYNTHETIC" if has_progress else "UNAVAILABLE"),
            "contractor": base if self.contractors else "UNAVAILABLE",
            "planned_completion": base if self.planned_completion else "UNAVAILABLE",
            "risk_score": "AI ASSESSMENT" if self.risk_assessments else "UNAVAILABLE"
        }


class ProjectFinancials(Base):
    __tablename__ = "project_financials"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    expenditure = Column(Numeric(15, 2), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    project = relationship("Project", back_populates="financials")

class ProjectProgress(Base):
    __tablename__ = "project_progress"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    percentage = Column(Integer, nullable=False)
    reported_at = Column(DateTime, server_default=func.now())

    project = relationship("Project", back_populates="progress")

class Contractor(Base):
    __tablename__ = "contractors"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)
    registration_id = Column(String, nullable=True)
    
    projects = relationship("ProjectContractor", back_populates="contractor")

class ProjectContractor(Base):
    __tablename__ = "project_contractors"
    project_id = Column(Integer, ForeignKey("projects.id"), primary_key=True)
    contractor_id = Column(Integer, ForeignKey("contractors.id"), primary_key=True)

    project = relationship("Project", back_populates="contractors")
    contractor = relationship("Contractor", back_populates="projects")

class RiskHistory(Base):
    __tablename__ = "risk_history"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    risk_score = Column(Integer, nullable=True)
    risk_level = Column(String, nullable=False)  # LOW, MEDIUM, HIGH, CRITICAL
    indicator_snapshot = Column(JSON, nullable=True)  # stores list of indicator dicts
    recorded_at = Column(DateTime, server_default=func.now())

    project = relationship("Project", back_populates="risk_history")

class PreSanctionAssessment(Base):
    __tablename__ = "pre_sanction_assessments"
    id = Column(Integer, primary_key=True, index=True)
    mp_id = Column(Integer, ForeignKey("mps.id"))
    proposed_category = Column(String)
    proposed_amount = Column(Float)
    description = Column(String)
    risk_score = Column(Integer)
    risk_level = Column(String)
    assessment_status = Column(String, nullable=True)
    assessment_coverage_pct = Column(Float, nullable=True)
    risk_reasons = Column(JSON, nullable=True)
    indicators = Column(JSON, nullable=True)
    provenance = Column(String, nullable=False, server_default="AI ASSESSMENT")
    engine_version = Column(String, nullable=True)
    assessed_at = Column(DateTime, default=datetime.datetime.utcnow)

class ReviewLog(Base):
    __tablename__ = "review_logs"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    reviewed_by = Column(String) # e.g. "District Collector"
    action = Column(String) # e.g. "FLAG", "CLEAR"
    comment = Column(String)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    project = relationship("Project", back_populates="review_logs")

class RiskAssessment(Base):
    __tablename__ = "risk_assessments"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    score = Column(Integer, nullable=True)
    overall_risk_level = Column(String, nullable=False) # LOW, MEDIUM, HIGH, CRITICAL, LIMITED
    assessment_status = Column(String, nullable=True)
    assessment_coverage_pct = Column(Float, nullable=True)
    assessable_indicator_count = Column(Integer, nullable=True)
    total_indicator_count = Column(Integer, nullable=True)
    risk_reasons = Column(JSON, nullable=True)
    engine_version = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    
    project = relationship("Project", back_populates="risk_assessments")
    indicators = relationship("RiskIndicator", back_populates="assessment")

class RiskIndicator(Base):
    __tablename__ = "risk_indicators"
    id = Column(Integer, primary_key=True, index=True)
    risk_assessment_id = Column(Integer, ForeignKey("risk_assessments.id"), nullable=False)
    indicator = Column(String, nullable=False)
    status = Column(String, nullable=False) # ASSESSABLE, NOT_ASSESSABLE
    severity = Column(String, nullable=False) # LOW, MEDIUM, HIGH, NOT_AVAILABLE
    score = Column(Integer, nullable=True)
    confidence = Column(Float, nullable=True)
    explanation = Column(Text, nullable=True)
    evidence = Column(JSON, nullable=True)
    data_provenance = Column(String, nullable=False, server_default="UNAVAILABLE")
    
    assessment = relationship("RiskAssessment", back_populates="indicators")

class Review(Base):
    __tablename__ = "reviews"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    reviewer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(String, nullable=False) # NEW, ACKNOWLEDGED, UNDER_REVIEW, ESCALATED, RESOLVED
    remarks = Column(Text, nullable=True)
    assigned_at = Column(DateTime, server_default=func.now())
    resolved_at = Column(DateTime, nullable=True)

    project = relationship("Project", back_populates="reviews")
    reviewer = relationship("User")

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action = Column(String, nullable=False)
    entity_type = Column(String, nullable=False)
    entity_id = Column(Integer, nullable=False)
    details = Column(Text, nullable=True)
    timestamp = Column(DateTime, server_default=func.now())

class ComplianceAssessment(Base):
    __tablename__ = "compliance_assessments"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    overall_status = Column(String, nullable=False)
    coverage_percentage = Column(Float, nullable=False)
    pass_count = Column(Integer, nullable=False, default=0)
    review_count = Column(Integer, nullable=False, default=0)
    not_assessable_count = Column(Integer, nullable=False, default=0)
    fail_count = Column(Integer, nullable=False, default=0)
    engine_version = Column(String, nullable=False, default="4.0.0")
    assessed_at = Column(DateTime, server_default=func.now())

    project = relationship("Project", back_populates="compliance_assessments")
    checks = relationship("ComplianceCheck", back_populates="assessment", cascade="all, delete-orphan")

class ComplianceCheck(Base):
    __tablename__ = "compliance_checks"
    id = Column(Integer, primary_key=True, index=True)
    assessment_id = Column(Integer, ForeignKey("compliance_assessments.id"), nullable=False)
    check_id = Column(String, nullable=False)
    check_name = Column(String, nullable=False)
    status = Column(String, nullable=False)  # PASS, REVIEW, NOT_ASSESSABLE, FAIL
    severity = Column(String, nullable=False)
    explanation = Column(Text, nullable=True)
    evidence = Column(JSON, nullable=True)
    provenance = Column(String, nullable=False, server_default="UNAVAILABLE")
    rule_type = Column(String, nullable=False)  # SYSTEM_VALIDATION, ANALYTICAL_CHECK, UNAVAILABLE
    required_fields = Column(JSON, nullable=True)
    available_fields = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    assessment = relationship("ComplianceAssessment", back_populates="checks")

class EarlyWarning(Base):
    __tablename__ = "early_warnings"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    warning_type = Column(String, nullable=False, index=True)
    warning_level = Column(String, nullable=False) # INFO, LOW, MEDIUM, HIGH, CRITICAL
    status = Column(String, nullable=False, default="OPEN", index=True) # OPEN, ACKNOWLEDGED, UNDER_REVIEW, RESOLVED, DISMISSED
    title = Column(String, nullable=False)
    explanation = Column(Text, nullable=False)
    trigger_signature = Column(String, nullable=False, unique=True, index=True)
    evidence = Column(JSON, nullable=True)
    provenance = Column(String, nullable=False, server_default="AI ASSESSMENT")
    assessment_coverage = Column(Float, nullable=True)
    confidence = Column(Float, nullable=True)
    detected_at = Column(DateTime, server_default=func.now())
    engine_version = Column(String, nullable=False)

    project = relationship("Project", back_populates="early_warnings")

class PredictiveCompletionAssessment(Base):
    __tablename__ = "predictive_completion_assessments"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    status = Column(String, nullable=False) # ASSESSABLE, LIMITED, NOT_ASSESSABLE
    risk_level = Column(String, nullable=True) # LOW, MEDIUM, HIGH, CRITICAL
    risk_score = Column(Integer, nullable=True)
    confidence = Column(String, nullable=True) # LOW, MEDIUM, HIGH
    coverage_pct = Column(Float, nullable=True)
    drivers = Column(JSON, nullable=True)
    evidence = Column(JSON, nullable=True)
    missing_data = Column(JSON, nullable=True)
    provenance = Column(String, nullable=False, server_default="AI ASSESSMENT")
    engine_version = Column(String, nullable=False, default="7.0.0")
    created_at = Column(DateTime, server_default=func.now())

    project = relationship("Project", back_populates="predictive_completion_assessments")


# ============================================================
# Phase 9 — Review Case, Case Notes, Case Audit Events
# ============================================================

_VALID_CASE_STATUSES = ('OPEN', 'UNDER_REVIEW', 'ACTION_REQUIRED', 'RESOLVED', 'DISMISSED')
_VALID_CASE_PRIORITIES = ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')

# Valid status transitions (server-side enforced)
CASE_TRANSITIONS = {
    'OPEN': ('UNDER_REVIEW', 'DISMISSED'),
    'UNDER_REVIEW': ('ACTION_REQUIRED', 'RESOLVED', 'DISMISSED'),
    'ACTION_REQUIRED': ('RESOLVED', 'UNDER_REVIEW'),
    'RESOLVED': (),       # terminal
    'DISMISSED': (),      # terminal
}

_VALID_AUDIT_ACTIONS = (
    'CASE_CREATED', 'CASE_ASSIGNED', 'STATUS_CHANGED', 'NOTE_ADDED',
    'EVIDENCE_ATTACHED', 'COMMENT_RECORDED', 'FLAG_RECORDED', 'CLEAR_RECORDED',
    'HALT_RECORDED', 'CASE_RESOLVED', 'CASE_DISMISSED',
)


class ReviewCase(Base):
    """Central case entity linking official AI signals to an investigation workflow."""
    __tablename__ = "review_cases"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    case_reference = Column(String, unique=True, nullable=False, index=True)  # MPLAD-REV-XXXX
    status = Column(String, nullable=False, default='OPEN', index=True)       # OPEN | UNDER_REVIEW | ACTION_REQUIRED | RESOLVED | DISMISSED
    priority = Column(String, nullable=False, default='MEDIUM')               # LOW | MEDIUM | HIGH | CRITICAL
    opened_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    assigned_to_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    summary = Column(Text, nullable=True)                                     # brief case description
    initial_note = Column(Text, nullable=True)                                # note provided at creation
    resolution_note = Column(Text, nullable=True)                             # filled on RESOLVED/DISMISSED
    triggering_signals = Column(JSON, nullable=True)                          # snapshot of signals at creation
    opened_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    resolved_at = Column(DateTime, nullable=True)

    # Relationships
    project = relationship("Project", back_populates="review_cases")
    opened_by = relationship("User", foreign_keys=[opened_by_id])
    assigned_to = relationship("User", foreign_keys=[assigned_to_id])
    notes = relationship("CaseNote", back_populates="case", order_by="CaseNote.created_at")
    audit_events = relationship("CaseAuditEvent", back_populates="case", order_by="CaseAuditEvent.created_at")


class CaseNote(Base):
    """Immutable official notes attached to a review case.

    Notes are append-only: no UPDATE or DELETE endpoint is provided.
    Provenance: OFFICIAL ACTION
    """
    __tablename__ = "case_notes"
    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("review_cases.id"), nullable=False, index=True)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    provenance = Column(String, nullable=False, default='OFFICIAL ACTION')
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    case = relationship("ReviewCase", back_populates="notes")
    author = relationship("User")


class CaseAuditEvent(Base):
    """Append-only audit trail for every official action on a review case.

    - No UPDATE or DELETE endpoint is exposed.
    - Every event records: WHO (user_id), WHAT (action), WHEN (created_at).
    - Provenance: OFFICIAL ACTION
    """
    __tablename__ = "case_audit_events"
    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("review_cases.id"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action = Column(String, nullable=False)          # one of _VALID_AUDIT_ACTIONS
    previous_status = Column(String, nullable=True)
    new_status = Column(String, nullable=True)
    comment = Column(Text, nullable=True)
    metadata_json = Column(JSON, nullable=True)      # additional structured context
    provenance = Column(String, nullable=False, default='OFFICIAL ACTION')
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    case = relationship("ReviewCase", back_populates="audit_events")
    user = relationship("User")
