from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..database import get_db
from .. import models, schemas
from ..auth_utils import get_current_user
from collections import defaultdict

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

@router.get("/stats", response_model=schemas.DashboardStatsResponse)
def get_dashboard_stats(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    # 1. MP Allocations (Official Government CSV)
    mps = db.query(models.MP).all()
    total_mps = len(mps)
    total_allocated_amount = sum((float(mp.allocated_amount) if mp.allocated_amount else 0.0) for mp in mps)

    # 2. Official Government Projects (eSAKSHI Work Dataset)
    projects = db.query(models.Project).outerjoin(models.DataSource).filter(
        (models.DataSource.source_type == "OFFICIAL") | (models.DataSource.id.is_(None))
    ).all()
    total_projects = len(projects)

    # Financials
    total_sanctioned = 0.0
    total_expenditure = 0.0

    for p in projects:
        s_amt = float(p.sanctioned_amount) if p.sanctioned_amount is not None and p.sanctioned_amount > 0 else 0.0
        total_sanctioned += s_amt

        exp_records = [float(f.expenditure) for f in p.financials if f.expenditure is not None and f.expenditure >= 0]
        if exp_records:
            total_expenditure += max(exp_records)

    utilization_pct = (total_expenditure / total_sanctioned * 100) if total_sanctioned > 0 else None

    # Portfolio Progress
    progress_sum = 0.0
    progress_count = 0
    for p in projects:
        prog_records = [pr.percentage for pr in p.progress if pr.percentage is not None and pr.percentage >= 0]
        if prog_records:
            progress_sum += max(prog_records)
            progress_count += 1

    average_progress = (progress_sum / progress_count) if progress_count > 0 else None

    # Risk Distribution & AI Risk Projects
    risk_distribution = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0, "LIMITED": 0}
    ai_risk_projects = set()

    for p in projects:
        if p.risk_assessments:
            latest_assessment = sorted(p.risk_assessments, key=lambda x: x.created_at, reverse=True)[0]
            level = latest_assessment.overall_risk_level.upper() if latest_assessment.overall_risk_level else "LOW"
            if level in risk_distribution:
                risk_distribution[level] += 1
            if level in ["MEDIUM", "HIGH", "CRITICAL"]:
                ai_risk_projects.add(p.id)

    # Human Review Flags
    human_flags = set()
    for p in projects:
        if p.review_logs:
            latest_review = sorted(p.review_logs, key=lambda x: x.created_at, reverse=True)[0]
            if latest_review.action == "FLAG":
                human_flags.add(p.id)

    # Delayed Projects
    delayed_projects = set(p.id for p in projects if p.status == "DELAYED")

    # Union: Projects Requiring Attention
    attention_projects = ai_risk_projects.union(human_flags).union(delayed_projects)

    # Category Breakdown
    categories = defaultdict(lambda: {"count": 0, "amount": 0.0})
    for p in projects:
        cat = p.category or "Unknown"
        amt = float(p.sanctioned_amount) if p.sanctioned_amount is not None and p.sanctioned_amount > 0 else 0.0
        categories[cat]["count"] += 1
        categories[cat]["amount"] += amt

    category_stats = []
    for cat, data in categories.items():
        category_stats.append(schemas.DashboardCategoryStat(
            category=cat,
            count=data["count"],
            total_amount=data["amount"]
        ))
    category_stats.sort(key=lambda x: x.count, reverse=True)

    # Compliance Intelligence Summary
    compliance_pass = 0
    compliance_review = 0
    compliance_na = 0
    compliance_assessed = 0

    # Compliance Map (Bulk to avoid N+1)
    comp_rows = db.query(
        models.ComplianceAssessment.project_id,
        models.ComplianceAssessment.overall_status
    ).order_by(models.ComplianceAssessment.assessed_at.desc()).all()
    
    comp_map = {}
    for row in comp_rows:
        if row[0] not in comp_map:
            comp_map[row[0]] = row[1]

    for p in projects:
        if p.id in comp_map:
            compliance_assessed += 1
            status = comp_map[p.id]
            if status == "PASS":
                compliance_pass += 1
            elif status in ("REVIEW", "PASS WITH LIMITED COVERAGE"):
                compliance_review += 1
            elif status == "NOT_ASSESSABLE":
                compliance_na += 1
            else:
                compliance_review += 1  # FAIL also routes to review

    from ..risk_engine.geo_utils import validate_coordinates
    valid_gps_count = sum(1 for p in projects if validate_coordinates(p.latitude, p.longitude) == 'VALID')
    gps_coverage = (valid_gps_count / total_projects * 100) if total_projects > 0 else 0.0

    # Early Warnings
    early_warnings = db.query(models.EarlyWarning).filter(models.EarlyWarning.status == "OPEN").all()
    ew_critical = ew_high = ew_medium = ew_low = 0
    ew_categories = {}

    for w in early_warnings:
        if w.warning_level == "CRITICAL":
            ew_critical += 1
        elif w.warning_level == "HIGH":
            ew_high += 1
        elif w.warning_level == "MEDIUM":
            ew_medium += 1
        elif w.warning_level == "LOW":
            ew_low += 1

        ew_categories[w.warning_type] = ew_categories.get(w.warning_type, 0) + 1

    top_ew_cats = [{"category": k, "count": v} for k, v in sorted(ew_categories.items(), key=lambda item: item[1], reverse=True)[:3]]

    ew_overview = schemas.EarlyWarningOverview(
        critical=ew_critical,
        high=ew_high,
        medium=ew_medium,
        low=ew_low,
        open_total=len(early_warnings),
        top_categories=top_ew_cats
    )

    pred_high = 0
    pred_med = 0
    pred_na = 0
    
    # Fast bulk map for predictive assessments
    pred_rows = db.query(
        models.PredictiveCompletionAssessment.project_id,
        models.PredictiveCompletionAssessment.risk_level,
        models.PredictiveCompletionAssessment.status
    ).order_by(models.PredictiveCompletionAssessment.created_at.desc()).all()
    
    pred_map = {}
    for row in pred_rows:
        if row[0] not in pred_map:
            pred_map[row[0]] = {"level": row[1], "status": row[2]}

    pred_na = 0
    pred_high = 0
    pred_med = 0
    
    # Priority aggregates
    pri_crit = pri_high = pri_med = pri_low = 0
    insufficient_ev = 0
    
    # Risk map for priority
    risk_rows = db.query(models.RiskAssessment.project_id, models.RiskAssessment.overall_risk_level, models.RiskAssessment.assessment_coverage_pct).all()
    risk_map = {row[0]: (row[1], row[2]) for row in risk_rows}
    
    # EW map for priority
    ew_map = {}
    for w in early_warnings:
        ew_map[w.project_id] = ew_map.get(w.project_id, 0) + 1

    for p in projects:
        # Predictive
        pred_lvl = None
        if p.id in pred_map:
            latest = pred_map[p.id]
            pred_lvl = latest["level"]
            if latest["status"] == "NOT_ASSESSABLE":
                pred_na += 1
            elif latest["level"] in ("HIGH", "CRITICAL"):
                pred_high += 1
            elif latest["level"] == "MEDIUM":
                pred_med += 1
                
        # Calculate Review Priority
        priority = "LOW"
        risk_lvl, risk_cov = risk_map.get(p.id, (None, 0.0))
        comp_status = comp_map.get(p.id, "NOT_ASSESSABLE")
        ew_count = ew_map.get(p.id, 0)

        if risk_lvl in ["HIGH", "CRITICAL"]:
            priority = "CRITICAL" if risk_lvl == "CRITICAL" else "HIGH"
        if comp_status in ["FAIL", "REVIEW"] and priority in ["LOW", "MEDIUM"]:
            priority = "HIGH"
        if ew_count > 0 and priority in ["LOW", "MEDIUM"]:
            priority = "HIGH"
        if pred_lvl in ["HIGH", "CRITICAL"] and priority in ["LOW", "MEDIUM"]:
            priority = "HIGH"
        if priority == "LOW" and risk_lvl == "MEDIUM":
            priority = "MEDIUM"
            
        if risk_cov and risk_cov < 30.0:
            insufficient_ev += 1
            if priority == "LOW":
                priority = "MEDIUM"

        if priority == "CRITICAL": pri_crit += 1
        elif priority == "HIGH": pri_high += 1
        elif priority == "MEDIUM": pri_med += 1
        else: pri_low += 1

    return schemas.DashboardStatsResponse(
        total_projects=total_projects,
        total_sanctioned_amount=total_sanctioned,
        total_expenditure=total_expenditure,
        utilization_percentage=utilization_pct,
        total_mps=total_mps,
        total_allocated_amount=total_allocated_amount,
        projects_with_progress=progress_count,
        average_progress=average_progress,
        ai_risk_projects=len(ai_risk_projects),
        human_review_flags=len(human_flags),
        delayed_projects=len(delayed_projects),
        projects_requiring_attention=len(attention_projects),
        gps_coverage_percentage=gps_coverage,
        risk_distribution=schemas.RiskDistribution(**risk_distribution),
        projects_by_category=category_stats,
        compliance_pass_count=compliance_pass if compliance_assessed > 0 else None,
        compliance_review_count=compliance_review if compliance_assessed > 0 else None,
        compliance_not_assessable_count=compliance_na if compliance_assessed > 0 else None,
        compliance_assessed_projects=compliance_assessed if compliance_assessed > 0 else None,
        early_warnings=ew_overview,
        predictive_high_risk=pred_high,
        predictive_medium_risk=pred_med,
        predictive_not_assessable=pred_na,
        review_priority_critical=pri_crit,
        review_priority_high=pri_high,
        review_priority_medium=pri_med,
        review_priority_low=pri_low,
        insufficient_evidence_projects=insufficient_ev
    )
