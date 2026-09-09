from sqlalchemy.orm import Session
from .. import models
import datetime
from .geo_utils import validate_coordinates, calculate_distance_km
import json
import hashlib


class EarlyWarningEngine:
    def __init__(self, db: Session):
        self.db = db
        self.engine_version = "6.1.0"
        self.current_time = datetime.datetime.utcnow()

    def generate_signature(self, project_id: int, warning_type: str, data: str) -> str:
        s = f"{project_id}:{warning_type}:{data}"
        return hashlib.sha256(s.encode()).hexdigest()

    def assess_project(self, project_id: int):
        p = self.db.query(models.Project).filter(models.Project.id == project_id).first()
        if not p:
            return []

        warnings_to_issue = []

        # Gather data
        risk_history = sorted(p.risk_history, key=lambda x: x.recorded_at)
        comp_history = sorted(p.compliance_assessments, key=lambda x: x.assessed_at)
        prog = sorted(p.progress, key=lambda x: x.reported_at)
        fin = sorted(p.financials, key=lambda x: x.updated_at)

        def add_warning(w_type, level, title, explanation, data_str, evidence, coverage):
            sig = self.generate_signature(project_id, w_type, data_str)
            existing = self.db.query(models.EarlyWarning).filter(
                models.EarlyWarning.trigger_signature == sig
            ).first()
            if not existing:
                w = models.EarlyWarning(
                    project_id=project_id,
                    warning_type=w_type,
                    warning_level=level,
                    title=title,
                    explanation=explanation,
                    trigger_signature=sig,
                    evidence=evidence,
                    assessment_coverage=coverage,
                    engine_version=self.engine_version,
                )
                self.db.add(w)
                warnings_to_issue.append(w)

        # ---------------------------------------------------------------
        # 1. RISK_ESCALATION
        # ---------------------------------------------------------------
        if len(risk_history) >= 2:
            prev = risk_history[-2]
            curr = risk_history[-1]
            levels = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
            prev_l = levels.get(prev.risk_level, 0)
            curr_l = levels.get(curr.risk_level, 0)
            if curr_l > prev_l and curr_l >= 2:
                add_warning(
                    "RISK_ESCALATION",
                    "HIGH" if curr_l >= 3 else "MEDIUM",
                    "Risk Escalation",
                    f"Risk level increased from {prev.risk_level} to {curr.risk_level} between the latest two available assessments.",
                    f"{prev.id}->{curr.id}",
                    {"prev_score": prev.risk_score, "curr_score": curr.risk_score},
                    None,
                )

        # ---------------------------------------------------------------
        # 2. RAPID_RISK_INCREASE
        #    Require >= 3 genuine non-null assessable risk_score values.
        #    Never convert NULL/NOT_ASSESSABLE to 0.
        # ---------------------------------------------------------------
        valid_risk_assessments = [rh for rh in risk_history if rh.risk_score is not None]
        if len(valid_risk_assessments) >= 3:
            s_first = valid_risk_assessments[0].risk_score
            s_last = valid_risk_assessments[-1].risk_score
            if s_last - s_first >= 40:
                first_id = valid_risk_assessments[0].id
                last_id = valid_risk_assessments[-1].id
                add_warning(
                    "RAPID_RISK_INCREASE",
                    "HIGH",
                    "Rapid Risk Increase",
                    "Risk score increased by 40 points across the recent assessment history.",
                    f"{first_id}->{last_id}",
                    {"increase": s_last - s_first},
                    None,
                )

        # ---------------------------------------------------------------
        # 3. REPEATED_ANOMALY
        # ---------------------------------------------------------------
        if len(risk_history) >= 3:
            indicator_counts: dict = {}
            for rh in risk_history[-3:]:
                if rh.indicator_snapshot:
                    for ind in rh.indicator_snapshot:
                        if ind.get("status") == "ASSESSABLE" and ind.get("severity") in ["HIGH", "MEDIUM"]:
                            name = ind.get("indicator")
                            indicator_counts[name] = indicator_counts.get(name, 0) + 1
            for ind_name, count in indicator_counts.items():
                if count >= 3:
                    add_warning(
                        "REPEATED_ANOMALY",
                        "MEDIUM",
                        f"Repeated Anomaly: {ind_name}",
                        f"The '{ind_name}' indicator has been flagged repeatedly across the last 3 assessments.",
                        f"{ind_name}_{risk_history[-1].id}",
                        {"indicator": ind_name, "count": count},
                        None,
                    )

        # ---------------------------------------------------------------
        # 4. PERSISTENT_HIGH_RISK
        # ---------------------------------------------------------------
        if len(risk_history) >= 3:
            if all(rh.risk_level in ["HIGH", "CRITICAL"] for rh in risk_history[-3:]):
                add_warning(
                    "PERSISTENT_HIGH_RISK",
                    "CRITICAL",
                    "Persistent High Risk",
                    "Project has maintained a HIGH or CRITICAL risk level for 3 consecutive assessments.",
                    f"phr_{risk_history[-1].id}",
                    {"consecutive_highs": 3},
                    None,
                )

        # ---------------------------------------------------------------
        # 5. COMPLIANCE_DETERIORATION
        # ---------------------------------------------------------------
        if len(comp_history) >= 2:
            prev_c = comp_history[-2]
            curr_c = comp_history[-1]
            if prev_c.overall_status == "PASS" and curr_c.overall_status in ["REVIEW", "FAIL"]:
                add_warning(
                    "COMPLIANCE_DETERIORATION",
                    "HIGH",
                    "Compliance Deterioration",
                    f"Compliance status worsened from {prev_c.overall_status} to {curr_c.overall_status}.",
                    f"comp_{prev_c.id}->{curr_c.id}",
                    {"prev": prev_c.overall_status, "curr": curr_c.overall_status},
                    curr_c.coverage_percentage,
                )

        # ---------------------------------------------------------------
        # 6. IMPLEMENTATION_STAGNATION
        #    status comparison is case-insensitive to handle "ONGOING"/"Ongoing"
        # ---------------------------------------------------------------
        if p.status and p.status.upper() == "ONGOING" and len(prog) >= 2:
            latest_prog_item = prog[-1]
            if latest_prog_item.percentage is not None and latest_prog_item.percentage < 100:
                days_since = (self.current_time - latest_prog_item.reported_at).days
                if days_since > 180:
                    add_warning(
                        "IMPLEMENTATION_STAGNATION",
                        "MEDIUM",
                        "Implementation Stagnation",
                        "No physical progress updates recorded in over 180 days.",
                        f"stag_{latest_prog_item.id}_{days_since}",
                        {"days_since_update": days_since, "current_progress": latest_prog_item.percentage},
                        None,
                    )

        # ---------------------------------------------------------------
        # 7. FINANCIAL_IMPLEMENTATION_MISMATCH
        # ---------------------------------------------------------------
        if prog and fin and p.sanctioned_amount:
            latest_prog_pct = prog[-1].percentage
            latest_exp_val = fin[-1].expenditure
            if latest_prog_pct is not None and latest_exp_val is not None:
                sanc = float(p.sanctioned_amount)
                if sanc > 0:
                    burn_rate = (float(latest_exp_val) / sanc) * 100
                    if burn_rate > 80 and latest_prog_pct < 40:
                        add_warning(
                            "FINANCIAL_IMPLEMENTATION_MISMATCH",
                            "HIGH",
                            "Financial / Implementation Mismatch",
                            f"High fund consumption ({burn_rate:.1f}%) with low physical progress ({latest_prog_pct}%).",
                            f"mismatch_{latest_prog_pct}_{burn_rate}",
                            {"burn_rate": burn_rate, "progress": latest_prog_pct},
                            None,
                        )

        # ---------------------------------------------------------------
        # 8. DATA_COVERAGE_CHANGE
        # ---------------------------------------------------------------
        if len(risk_history) >= 2:
            prev_rh = risk_history[-2]
            curr_rh = risk_history[-1]
            # Only use genuine scores — do NOT fall back to 0 for None
            if prev_rh.risk_score is not None and curr_rh.risk_score is not None:
                prev_s = prev_rh.risk_score
                curr_s = curr_rh.risk_score
                curr_ass = (
                    self.db.query(models.RiskAssessment)
                    .filter(models.RiskAssessment.project_id == project_id)
                    .order_by(models.RiskAssessment.created_at.desc())
                    .first()
                )
                if curr_ass and curr_ass.assessment_coverage_pct:
                    curr_cov = curr_ass.assessment_coverage_pct
                    if curr_s > prev_s + 20 and curr_cov > 50:
                        add_warning(
                            "DATA_COVERAGE_CHANGE",
                            "INFO",
                            "Coverage-Aware Risk Increase",
                            "Risk increased while assessment coverage also increased; the change should be interpreted alongside the improved evidence base.",
                            f"cov_{curr_ass.id}",
                            {"coverage": curr_cov, "score_change": curr_s - prev_s},
                            curr_cov,
                        )

        # ---------------------------------------------------------------
        # 9. BURN RATE WARNINGS
        # ---------------------------------------------------------------
        if fin and prog and p.sanctioned_amount:
            latest_exp_val = fin[-1].expenditure
            latest_prog_pct = prog[-1].percentage
            if latest_exp_val is not None and latest_prog_pct is not None:
                sanc = float(p.sanctioned_amount)
                if sanc > 0:
                    burn_rate = (float(latest_exp_val) / sanc) * 100
                    if burn_rate >= 80 and latest_prog_pct < 50:
                        add_warning(
                            "Burn Rate",
                            "HIGH",
                            "High Burn Rate",
                            f"Burn rate is {burn_rate:.1f}% with progress {latest_prog_pct}%.",
                            f"burn_{p.id}_{burn_rate:.1f}",
                            None,
                            None,
                        )
                    elif burn_rate >= 70 and latest_prog_pct < 70:
                        add_warning(
                            "Burn Rate",
                            "MEDIUM",
                            "Medium Burn Rate",
                            f"Burn rate is {burn_rate:.1f}% with progress {latest_prog_pct}%.",
                            f"burn_{p.id}_{burn_rate:.1f}",
                            None,
                            None,
                        )

        # ---------------------------------------------------------------
        # 10. DEADLINE WARNINGS
        # ---------------------------------------------------------------
        if p.planned_completion and p.status and p.status.upper() != "COMPLETED":
            days_until = (p.planned_completion - self.current_time.date()).days
            if days_until < 0:
                add_warning(
                    "Deadline",
                    "HIGH",
                    "Project Overdue",
                    f"Planned completion was {abs(days_until)} days ago.",
                    f"deadline_{p.id}_{days_until}",
                    None,
                    None,
                )
            elif days_until <= 90:
                prog_pct = prog[-1].percentage if prog else None
                if prog_pct is not None and prog_pct < 70:
                    add_warning(
                        "Deadline",
                        "MEDIUM",
                        "Approaching Deadline",
                        f"{days_until} days left with progress {prog_pct}%.",
                        f"deadline_{p.id}_{days_until}",
                        None,
                        None,
                    )

        # ---------------------------------------------------------------
        # 11. DATA ANOMALY WARNINGS
        # ---------------------------------------------------------------
        for f_item in fin:
            if f_item.expenditure is not None and f_item.expenditure < 0:
                add_warning(
                    "Data Anomaly",
                    "LOW",
                    "Negative Expenditure",
                    "Expenditure value is negative.",
                    f"data_anom_{p.id}_{f_item.id}",
                    {"value": float(f_item.expenditure)},
                    None,
                )
        for pr_item in prog:
            if pr_item.percentage is not None and (pr_item.percentage < 0 or pr_item.percentage > 100):
                add_warning(
                    "Data Anomaly",
                    "LOW",
                    "Invalid Progress",
                    "Invalid progress percentage: value is out of valid range (0–100).",
                    f"data_anom_{p.id}_{pr_item.id}",
                    {"value": pr_item.percentage},
                    None,
                )

        # ---------------------------------------------------------------
        # 12. STAGNATION (generic — not tied to GPS validity)
        # ---------------------------------------------------------------
        if prog:
            latest_prog_item = prog[-1]
            if latest_prog_item.percentage is not None and latest_prog_item.percentage < 100:
                days_since = (self.current_time - latest_prog_item.reported_at).days
                if days_since > 180:
                    add_warning(
                        "Stagnation",
                        "MEDIUM",
                        "Progress Stagnation",
                        f"No progress update for {days_since} days.",
                        f"stagn_{p.id}_{days_since}",
                        None,
                        None,
                    )

        # ---------------------------------------------------------------
        # SPATIAL SIGNALS
        # Only OFFICIAL provenance projects participate in official analytics.
        # ---------------------------------------------------------------
        geo_status = validate_coordinates(p.latitude, p.longitude)

        # COORDINATE_VALIDATION_ISSUE: project claims OFFICIAL coords but they are invalid
        if (
            geo_status == "INVALID"
            and p.latitude is not None
            and p.gps_provenance == "OFFICIAL"
        ):
            add_warning(
                "COORDINATE_VALIDATION_ISSUE",
                "LOW",
                "Coordinate Validation Issue",
                "Official coordinates fall outside valid geographic bounds.",
                f"coord_{p.latitude}_{p.longitude}",
                {"lat": p.latitude, "lng": p.longitude},
                None,
            )

        elif geo_status == "VALID" and p.gps_provenance == "OFFICIAL":
            # Find other OFFICIAL projects with VALID coordinates
            nearby_projects = (
                self.db.query(models.Project)
                .filter(
                    models.Project.id != project_id,
                    models.Project.gps_provenance == "OFFICIAL",
                )
                .all()
            )

            cluster_count = 0
            duplicate_suspects = 0

            for other in nearby_projects:
                if validate_coordinates(other.latitude, other.longitude) == "VALID":
                    dist = calculate_distance_km(
                        p.latitude, p.longitude, other.latitude, other.longitude
                    )
                    if dist is not None:
                        if dist < 2.0:
                            cluster_count += 1
                        if dist < 0.5:
                            if p.category and other.category and p.category == other.category:
                                duplicate_suspects += 1

            # NEAR_DUPLICATE_LOCATION
            if duplicate_suspects >= 1:
                add_warning(
                    "NEAR_DUPLICATE_LOCATION",
                    "HIGH",
                    "Potential duplicate-location pattern",
                    "Potential duplicate-location pattern: Nearby project with similar category detected.",
                    f"dup_{duplicate_suspects}_{p.id}",
                    {"duplicates": duplicate_suspects},
                    None,
                )

            # SPATIAL_CLUSTER: subject + 4 other qualifying projects = 5 total
            if cluster_count >= 4:
                add_warning(
                    "SPATIAL_CLUSTER",
                    "MEDIUM",
                    "Spatial Cluster",
                    f"{cluster_count + 1} projects are geographically concentrated.",
                    f"clus_{cluster_count}_{p.id}",
                    {"cluster_size": cluster_count + 1},
                    None,
                )

        self.db.flush()

        # ---------------------------------------------------------------
        # MULTI_SIGNAL_CONVERGENCE: fire when >= 3 distinct OPEN warning types
        # ---------------------------------------------------------------
        open_warnings = (
            self.db.query(models.EarlyWarning)
            .filter(
                models.EarlyWarning.project_id == project_id,
                models.EarlyWarning.status == "OPEN",
                models.EarlyWarning.warning_type != "MULTI_SIGNAL_CONVERGENCE",
            )
            .all()
        )
        distinct_types = set(w.warning_type for w in open_warnings)
        if len(distinct_types) >= 3:
            signals = sorted(distinct_types)
            add_warning(
                "MULTI_SIGNAL_CONVERGENCE",
                "CRITICAL",
                "Multi-Signal Convergence",
                f"Multiple independent signals detected: {', '.join(signals)}",
                f"multi_{len(signals)}_{hashlib.md5(''.join(signals).encode()).hexdigest()}",
                {"signals": signals},
                None,
            )

        self.db.commit()
        return warnings_to_issue
