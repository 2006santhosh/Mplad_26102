from pydantic import BaseModel, constr, validator
from typing import List, Optional, Dict
from datetime import date, datetime

class ReviewLogCreate(BaseModel):
    reviewed_by: str
    action: str
    comment: str
    
    @validator('action')
    def validate_action(cls, v):
        allowed = ['COMMENT', 'FLAG', 'CLEAR', 'HALT']
        if v not in allowed:
            raise ValueError(f"Action must be one of {allowed}")
        return v
        
    @validator('comment')
    def validate_comment(cls, v):
        if not v or not v.strip():
            raise ValueError("Comment cannot be empty or whitespace")
        return v.strip()

class ReviewLogResponse(BaseModel):
    id: int
    project_id: int
    reviewed_by: str
    action: str
    comment: str
    created_at: datetime

    class Config:
        from_attributes = True

class DashboardCategoryStat(BaseModel):
    category: str
    count: int
    total_amount: float

class RiskDistribution(BaseModel):
    LOW: int = 0
    MEDIUM: int = 0
    HIGH: int = 0
    CRITICAL: int = 0
    LIMITED: int = 0

class DashboardStatsResponse(BaseModel):
    total_projects: Optional[int] = None
    total_sanctioned_amount: Optional[float] = None
    total_expenditure: Optional[float] = None
    utilization_percentage: Optional[float] = None
    
    total_mps: Optional[int] = None
    total_allocated_amount: Optional[float] = None
    
    projects_with_progress: int
    average_progress: Optional[float] = None
    
    ai_risk_projects: int
    human_review_flags: int
    delayed_projects: int
    projects_requiring_attention: int
    gps_coverage_percentage: Optional[float] = None
    
    risk_distribution: RiskDistribution
    projects_by_category: List[DashboardCategoryStat]
    early_warnings: Optional["EarlyWarningOverview"] = None
    
    # Compliance Intelligence Summary
    compliance_pass_count: Optional[int] = None
    compliance_review_count: Optional[int] = None
    compliance_not_assessable_count: Optional[int] = None
    compliance_assessed_projects: Optional[int] = None

    predictive_high_risk: Optional[int] = None
    predictive_medium_risk: Optional[int] = None
    predictive_not_assessable: Optional[int] = None

class EarlyWarningOverview(BaseModel):
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    open_total: int = 0
    top_categories: List[dict] = []

    # Inject into DashboardStatsResponse later


class ProjectBase(BaseModel):
    category: Optional[str] = None
    sanctioned_amount: Optional[float] = None
    location: Optional[str] = None
    planned_start: Optional[date] = None
    planned_completion: Optional[date] = None
    status: Optional[str] = None
    work_id: Optional[str] = None
    work_stage: Optional[str] = None
    district: Optional[str] = None
    constituency: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    gps_provenance: Optional[str] = "UNAVAILABLE"

class ProjectMapItem(BaseModel):
    project_id: int
    latitude: float
    longitude: float
    gps_provenance: str
    risk_level: Optional[str] = None
    risk_score: Optional[int] = None
    warning_count: Optional[int] = 0

class MapResponse(BaseModel):
    projects: List[ProjectMapItem]
    gps_coverage_percentage: float
    total_projects: int
    valid_gps_count: int
    unavailable_gps_count: int

class ProjectResponse(ProjectBase):
    id: int
    mp_id: int
    data_source_id: int
    actual_completion: Optional[date] = None
    source_type: Optional[str] = None
    mp_name: Optional[str] = None
    early_warning_count: Optional[int] = 0
    progress_pct: Optional[int] = None
    progress_proxy_label: Optional[str] = "Analytical Progress Proxy — derived from official WORK_STAGE"
    latest_risk_score: Optional[int] = None
    latest_risk_level: Optional[str] = None
    description: Optional[str] = None
    provenance: Optional[dict] = None
    predictive_risk_level: Optional[str] = None
    
    class Config:
        from_attributes = True

class ProjectDetailResponse(ProjectResponse):
    progress_pct: Optional[int] = 0
    expenditure: Optional[float] = 0.0
    latest_risk_score: Optional[int] = None
    latest_risk_level: Optional[str] = None
    source_type: Optional[str] = None
    description: Optional[str] = None
    work_category: Optional[str] = None
    progress_proxy_label: Optional[str] = "Analytical Progress Proxy — derived from official WORK_STAGE"
    provenance: Optional[dict] = None

class RiskIndicatorSchema(BaseModel):
    indicator: str
    status: str
    severity: str
    score: Optional[int] = None
    confidence: Optional[float] = None
    explanation: str
    evidence: dict
    data_provenance: str

class AssessmentCoverage(BaseModel):
    assessable: int
    total: int
    percentage: float

class RiskAssessmentResponse(BaseModel):
    score: Optional[int] = None
    level: str
    assessment_status: str
    assessment_coverage: AssessmentCoverage
    assessable_indicator_count: int
    total_indicator_count: int
    risk_reasons: List[str]
    indicators: List[RiskIndicatorSchema]
class PreSanctionRequest(BaseModel):
    category: str
    sanctioned_amount: float
    location: str
    planned_duration_days: int
    contractor_id: Optional[int] = None

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    role: str

# New schemas for compliance, trends, early warning, predictive risk, and risk history

class ComplianceCheckSchema(BaseModel):
    check_id: str
    check_name: str
    status: str  # PASS, REVIEW, NOT_ASSESSABLE, FAIL
    severity: str
    explanation: str
    evidence: dict
    provenance: str
    required_fields: List[str]
    available_fields: List[str]
    rule_type: str  # SYSTEM_VALIDATION, ANALYTICAL_CHECK, UNAVAILABLE

class ComplianceAssessmentResponse(BaseModel):
    project_id: int
    overall_status: str
    coverage_percentage: float
    pass_count: int
    review_count: int
    not_assessable_count: int
    fail_count: int
    total_checks: int
    checks: List[ComplianceCheckSchema]
    engine_version: Optional[str] = None

class TrendDataPoint(BaseModel):
    date: date
    value: float
    is_invalid: bool = False
    note: Optional[str] = None

class TrendResponse(BaseModel):
    type: str  # e.g., "expenditure", "risk", "delay"
    data: List[TrendDataPoint]
    source_type: str

class EarlyWarningItem(BaseModel):
    id: int
    warning_type: str
    warning_level: str
    status: str
    title: str
    explanation: str
    trigger_signature: str
    evidence: Optional[Dict] = None
    provenance: Optional[str] = None
    assessment_coverage: Optional[float] = None
    confidence: Optional[float] = None
    detected_at: datetime
    engine_version: str

class EarlyWarningResponse(BaseModel):
    project_id: int
    warnings: List[EarlyWarningItem]
    source_type: str

class ProjectedCompletionRiskResponse(BaseModel):
    project_id: int
    risk_score: int
    risk_level: str
    explanation: str
    source_type: str
    projected_date: Optional[date] = None
    planned_date: Optional[date] = None
    velocity: Optional[float] = None
    delay_days: Optional[int] = None

class PredictiveCompletionResponse(BaseModel):
    status: str
    risk_level: Optional[str] = None
    risk_score: Optional[int] = None
    confidence: Optional[str] = None
    coverage_pct: Optional[float] = None
    drivers: List[str] = []
    evidence: dict = {}
    missing_data: List[str] = []
    provenance: str = "AI ASSESSMENT"
    engine_version: str = "7.0.0"

class RiskHistoryAssessment(BaseModel):
    assessment_id: int
    assessed_at: datetime
    risk_score: Optional[int] = None
    risk_level: str
    assessment_status: Optional[str] = None
    assessment_coverage: Optional[AssessmentCoverage] = None
    risk_reasons: List[str] = []
    engine_version: Optional[str] = None

class IndicatorHistoryPoint(BaseModel):
    assessment_id: int
    assessed_at: datetime
    status: str
    score: Optional[int] = None
    confidence: Optional[float] = None
    severity: str
    explanation: Optional[str] = None

class IndicatorTrendResponse(BaseModel):
    indicator: str
    history: List[IndicatorHistoryPoint]
    trend: str
    explanation: str

class RiskHistoryResponse(BaseModel):
    project_id: int
    assessments: List[RiskHistoryAssessment]
    indicator_trends: List[IndicatorTrendResponse]
    risk_trend_status: str # INCREASING, DECREASING, STABLE, VOLATILE, INSUFFICIENT_HISTORY
    risk_trend_explanation: str
    score_change_absolute: Optional[int] = None

class ComplianceHistoryAssessment(BaseModel):
    assessment_id: int
    assessed_at: datetime
    overall_status: str
    coverage_percentage: float
    pass_count: int
    review_count: int
    not_assessable_count: int
    fail_count: int
    engine_version: Optional[str] = None

class ComplianceHistoryResponse(BaseModel):
    project_id: int
    assessments: List[ComplianceHistoryAssessment]
    trend_status: str
    trend_explanation: str

class ComparisonMetric(BaseModel):
    metric_name: str
    project_value: Optional[float] = None
    peer_average: Optional[float] = None
    difference_percentage: Optional[float] = None
    is_anomaly: bool = False

class ProjectComparisonResponse(BaseModel):
    project_id: int
    peer_group_name: str
    peer_count: int
    metrics: List[ComparisonMetric]

class GISProjectItem(BaseModel):
    project_id: int
    location: str
    category: str
    sanctioned_amount: Optional[float] = None
    latitude: float
    longitude: float

class GISCluster(BaseModel):
    cluster_id: str
    center_latitude: float
    center_longitude: float
    project_count: int
    total_amount: float
    projects: List[GISProjectItem]

class GISResponse(BaseModel):
    clusters: List[GISCluster]
    total_valid_projects: int

