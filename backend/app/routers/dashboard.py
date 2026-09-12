from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..database import get_db
from .. import models, schemas
from ..auth_utils import get_current_user
from ..services.review_priority import calculate_review_priority
from ..official_data import OFFICIAL, official_projects_query
from collections import defaultdict

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

@router.get("/stats", response_model=schemas.DashboardStatsResponse)
def get_dashboard_stats(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    # 1. MP Allocations (Official Government CSV)
    mps = db.query(models.MP).join(models.DataSource).filter(models.DataSource.source_type == OFFICIAL).all()
    total_mps = len(mps)
    total_allocated_amount = sum((float(mp.allocated_amount) if mp.allocated_amount else 0.0) for mp in mps)

    # 2. Official Government Projects (eSAKSHI Work Dataset)
    projects = official_projects_query(db).all()
    total_projects = len(projects)

    # Financials
    total_sanctioned = 0.0
    for p in projects:
        s_amt = float(p.sanctioned_amount) if p.sanctioned_amount is not None and p.sanctioned_amount > 0 else 0.0
        total_sanctioned += s_amt

    project_ids = [p.id for p in projects]

    # --- N+1 Bulk Maps ---
    # 1. Financials Map
    fin_rows = db.query(models.ProjectFinancials.project_id, models.ProjectFinancials.expenditure).filter(
        models.ProjectFinancials.project_id.in_(project_ids)
    ).all()
    fin_map = defaultdict(list)
    for row in fin_rows:
        if row.expenditure is not None and row.expenditure >= 0:
            fin_map[row.project_id].append(float(row.expenditure))

    # 2. Progress Map
    prog_rows = db.query(models.ProjectProgress.project_id, models.ProjectProgress.percentage).filter(
        models.ProjectProgress.project_id.in_(project_ids)
    ).all()
    prog_map = defaultdict(list)
    for row in prog_rows:
        if row.percentage is not None and row.percentage >= 0:
            prog_map[row.project_id].append(float(row.percentage))

    # 3. Latest Risk Assessment Map
    risk_assessments = db.query(models.RiskAssessment).filter(
        models.RiskAssessment.project_id.in_(project_ids)
    ).order_by(
        models.RiskAssessment.created_at.desc(),
        models.RiskAssessment.id.desc(),
    ).all()
    
    latest_assessments = {}
    for ra in risk_assessments:
        if ra.project_id not in latest_assessments:
            latest_assessments[ra.project_id] = ra

    latest_assessment_ids = [ra.id for ra in latest_assessments.values()]

    # Risk Distribution & AI Risk Projects
    risk_distribution = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0, "LIMITED": 0}
    ai_risk_projects = set()
    
    for pid, ra in latest_assessments.items():
        level = ra.overall_risk_level.upper() if ra.overall_risk_level else "LOW"
        if level in risk_distribution:
            risk_distribution[level] += 1
        if level in ["MEDIUM", "HIGH", "CRITICAL"]:
            ai_risk_projects.add(pid)

    # 4. Actual Risk Indicators for Breakdown
    active_indicators = db.query(models.RiskIndicator.indicator, models.RiskIndicator.severity).filter(
        models.RiskIndicator.risk_assessment_id.in_(latest_assessment_ids),
        models.RiskIndicator.severity.in_(["MEDIUM", "HIGH", "CRITICAL"])
    ).all()
    
    signal_breakdown = defaultdict(int)
    for ind in active_indicators:
        signal_breakdown[ind.indicator] += 1
        
    signal_breakdown_list = [{"name": k, "count": v} for k, v in sorted(signal_breakdown.items(), key=lambda x: x[1], reverse=True)]
    ai_risk_signal_total = sum(item["count"] for item in signal_breakdown_list)

    # 5. Human Review Flags Map
    review_rows = db.query(models.ReviewLog.project_id, models.ReviewLog.action, models.ReviewLog.created_at).filter(
        models.ReviewLog.project_id.in_(project_ids)
    ).all()
    latest_reviews = {}
    for row in review_rows:
        pid, action, cat = row.project_id, row.action, row.created_at
        if pid not in latest_reviews or cat > latest_reviews[pid][1]:
            latest_reviews[pid] = (action, cat)

    human_flags = set()
    for pid, (action, _) in latest_reviews.items():
        if action == "FLAG":
            human_flags.add(pid)

    # Calculate Utilization
    total_expenditure = 0.0
    for pid in project_ids:
        if pid in fin_map:
            total_expenditure += max(fin_map[pid])

    utilization_pct = (total_expenditure / total_sanctioned * 100) if total_sanctioned > 0 else None

    # Calculate Progress
    progress_sum = 0.0
    progress_count = 0
    for pid in project_ids:
        if pid in prog_map:
            progress_sum += max(prog_map[pid])
            progress_count += 1

    average_progress = (progress_sum / progress_count) if progress_count > 0 else None

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

    def grouped_counts(values):
        counts = defaultdict(int)
        for value in values:
            counts[value or "Unknown"] += 1
        return [{"name": name, "count": count} for name, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:10]]

    portfolio_breakdown = {
        "states": grouped_counts([p.mp.state if p.mp else None for p in projects]),
        "districts": grouped_counts([p.district for p in projects]),
        "stages": grouped_counts([p.work_stage for p in projects]),
    }

    # Compliance Intelligence Summary
    compliance_pass = 0
    compliance_review = 0
    compliance_na = 0
    compliance_assessed = 0

    # Compliance Map (Bulk to avoid N+1)
    comp_rows = db.query(
        models.ComplianceAssessment.project_id,
        models.ComplianceAssessment.overall_status
    ).order_by(
        models.ComplianceAssessment.assessed_at.desc(),
        models.ComplianceAssessment.id.desc(),
    ).all()
    
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
    early_warnings = db.query(models.EarlyWarning).filter(
        models.EarlyWarning.project_id.in_(project_ids),
        models.EarlyWarning.status.in_(["OPEN", "ACKNOWLEDGED", "UNDER_REVIEW"])
    ).order_by(models.EarlyWarning.detected_at.desc(), models.EarlyWarning.id.desc()).all()
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
    ).order_by(
        models.PredictiveCompletionAssessment.created_at.desc(),
        models.PredictiveCompletionAssessment.id.desc(),
    ).all()
    
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
    risk_rows = db.query(models.RiskAssessment.project_id, models.RiskAssessment.overall_risk_level, models.RiskAssessment.assessment_coverage_pct).order_by(
        models.RiskAssessment.created_at.desc(), models.RiskAssessment.id.desc()
    ).all()
    risk_map = {}
    for row in risk_rows:
        if row[0] not in risk_map:
            risk_map[row[0]] = (row[1], row[2])
    
    # EW map for priority
    ew_map = {}
    for w in early_warnings:
        ew_map.setdefault(w.project_id, []).append(w.warning_level)

    # Risk history map for trend
    history_rows = db.query(models.RiskHistory.project_id, models.RiskHistory.risk_score).order_by(
        models.RiskHistory.recorded_at.asc(), models.RiskHistory.id.asc()
    ).all()
    history_map = {}
    for pid, score in history_rows:
        history_map.setdefault(pid, []).append(score)
        
    def _risk_trend(scores: list[int | None]) -> dict:
        valid = [score for score in scores if score is not None]
        if len(valid) < 2:
            return {"trend": "INSUFFICIENT_HISTORY", "explanation": "Not enough historical risk assessments to determine a trend."}
        delta = valid[-1] - valid[0]
        if delta > 10:
            return {"trend": "INCREASING", "explanation": "Risk has increased significantly over the available assessment history."}
        if delta < -10:
            return {"trend": "DECREASING", "explanation": "Risk has decreased over the available assessment history."}
        return {"trend": "STABLE", "explanation": "Risk levels have remained stable over the available assessment history."}

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
                
        # Calculate Review Priority through the canonical service.
        risk_lvl, risk_cov = risk_map.get(p.id, (None, None))
        comp_status = comp_map.get(p.id, "NOT_ASSESSABLE")
        warning_levels = ew_map.get(p.id, [])
        warnings_data = [{"level": level, "type": "Early Warning", "explanation": "Open analytical warning."} for level in warning_levels]

        priority = calculate_review_priority(
            overall_risk={"level": risk_lvl, "score": None, "coverage": risk_cov},
            risk_trend=_risk_trend(history_map.get(p.id, [])),
            compliance={"status": comp_status},
            open_warnings=warnings_data,
            completion_risk={"level": pred_lvl, "confidence": None},
        )
        if risk_cov is not None and risk_cov < 30.0:
            insufficient_ev += 1
        priority_level = priority["level"]

        if priority_level == "CRITICAL": pri_crit += 1
        elif priority_level == "HIGH": pri_high += 1
        elif priority_level == "MEDIUM": pri_med += 1
        else: pri_low += 1

    return schemas.DashboardStatsResponse(
        total_projects=total_projects,
        total_projects_provenance="OFFICIAL",
        total_sanctioned_amount=total_sanctioned,
        total_sanctioned_amount_provenance="DERIVED",
        total_expenditure=total_expenditure,
        total_expenditure_provenance="DERIVED",
        utilization_percentage=utilization_pct,
        utilization_percentage_provenance="DERIVED",
        total_mps=total_mps,
        total_mps_provenance="OFFICIAL",
        total_allocated_amount=total_allocated_amount,
        total_allocated_amount_provenance="DERIVED",
        projects_with_progress=progress_count,
        projects_with_progress_provenance="DERIVED",
        average_progress=average_progress,
        average_progress_provenance="DERIVED",
        ai_risk_projects=len(ai_risk_projects),
        ai_risk_projects_provenance="DERIVED",
        ai_risk_signal_total=ai_risk_signal_total,
        ai_risk_signal_total_provenance="DERIVED",
        ai_risk_signal_breakdown=signal_breakdown_list,
        ai_risk_signal_breakdown_provenance="DERIVED",
        human_review_flags=len(human_flags),
        human_review_flags_provenance="DERIVED",
        delayed_projects=len(delayed_projects),
        delayed_projects_provenance="DERIVED",
        projects_requiring_attention=len(attention_projects),
        projects_requiring_attention_provenance="DERIVED",
        gps_coverage_percentage=gps_coverage,
        gps_coverage_percentage_provenance="DERIVED",
        risk_distribution=schemas.RiskDistribution(**risk_distribution),
        risk_distribution_provenance="DERIVED",
        projects_by_category=category_stats,
        projects_by_category_provenance="DERIVED",
        early_warnings=ew_overview,
        early_warnings_provenance="DERIVED",
        compliance_pass_count=compliance_pass if compliance_assessed > 0 else None,
        compliance_pass_count_provenance="DERIVED",
        compliance_review_count=compliance_review if compliance_assessed > 0 else None,
        compliance_review_count_provenance="DERIVED",
        compliance_not_assessable_count=compliance_na if compliance_assessed > 0 else None,
        compliance_not_assessable_count_provenance="DERIVED",
        compliance_assessed_projects=compliance_assessed if compliance_assessed > 0 else None,
        compliance_assessed_projects_provenance="DERIVED",
        predictive_high_risk=pred_high,
        predictive_high_risk_provenance="DERIVED",
        predictive_medium_risk=pred_med,
        predictive_medium_risk_provenance="DERIVED",
        predictive_not_assessable=pred_na,
        predictive_not_assessable_provenance="DERIVED",
        review_priority_critical=pri_crit,
        review_priority_critical_provenance="DERIVED",
        review_priority_high=pri_high,
        review_priority_high_provenance="DERIVED",
        review_priority_medium=pri_med,
        review_priority_medium_provenance="DERIVED",
        review_priority_low=pri_low,
        review_priority_low_provenance="DERIVED",
        insufficient_evidence_projects=insufficient_ev,
        insufficient_evidence_projects_provenance="DERIVED",
        portfolio_breakdown=portfolio_breakdown,
        portfolio_breakdown_provenance="DERIVED"
    )


