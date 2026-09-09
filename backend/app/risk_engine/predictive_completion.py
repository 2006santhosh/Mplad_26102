from sqlalchemy.orm import Session
from .. import models
import datetime

class PredictiveCompletionRiskEngine:
    def __init__(self, db: Session):
        self.db = db
        self.engine_version = "7.0.0"
        self.current_time = datetime.datetime.utcnow()

    def assess(self, project_id: int) -> dict:
        p = self.db.query(models.Project).filter(models.Project.id == project_id).first()
        if not p:
            return self._not_assessable("Project not found.")

        drivers = []
        evidence = {}
        missing_data = []
        score = 0

        # 1. Gather Data
        prog = sorted(p.progress, key=lambda x: x.reported_at)
        fin = sorted(p.financials, key=lambda x: x.updated_at)
        risk_history = sorted(p.risk_assessments, key=lambda x: x.created_at)
        comp_history = sorted(p.compliance_assessments, key=lambda x: x.assessed_at)

        latest_prog_pct = prog[-1].percentage if prog and prog[-1].percentage is not None else None
        latest_exp_val = float(fin[-1].expenditure) if fin and fin[-1].expenditure is not None else None
        sanc_amount = float(p.sanctioned_amount) if p.sanctioned_amount else None

        # Data Sufficiency Checks
        if latest_prog_pct is None:
            missing_data.append("Analytical Progress Proxy unavailable")
        
        valid_risk_assessments = [rh for rh in risk_history if rh.score is not None]
        if len(valid_risk_assessments) < 2:
            missing_data.append("Insufficient historical risk assessments")

        if not comp_history:
            missing_data.append("Compliance assessment unavailable")

        if len(missing_data) >= 2:
            return self._not_assessable("Insufficient evidence is available to estimate completion risk.", missing_data)

        # 2. Features Evaluation
        
        # A. Current Work Stage & Implementation Stagnation
        if p.work_stage:
            evidence["work_stage"] = p.work_stage
            
        if p.status and p.status.upper() == "ONGOING" and prog:
            latest_prog_item = prog[-1]
            if latest_prog_item.percentage is not None and latest_prog_item.percentage < 100:
                days_since = (self.current_time - latest_prog_item.reported_at).days
                if days_since > 180:
                    drivers.append("Implementation shows prolonged stagnation (>180 days with no Analytical Progress Proxy update)")
                    score += 30
                    evidence["days_since_update"] = days_since
                elif days_since > 90:
                    drivers.append("Implementation shows early signs of stagnation (>90 days)")
                    score += 15
                    evidence["days_since_update"] = days_since

        # B. Risk Trajectory
        if len(valid_risk_assessments) >= 2:
            s_first = valid_risk_assessments[0].score
            s_last = valid_risk_assessments[-1].score
            evidence["historical_risk_trend"] = f"{s_first} -> {s_last}"
            if s_last - s_first >= 20:
                drivers.append("Risk trajectory is significantly increasing")
                score += 25
            elif s_last - s_first >= 10:
                drivers.append("Risk trajectory is increasing")
                score += 15

        # C. Current Risk
        if valid_risk_assessments:
            curr = valid_risk_assessments[-1]
            evidence["current_risk_level"] = curr.overall_risk_level
            if curr.overall_risk_level == "CRITICAL":
                drivers.append("Current risk level is CRITICAL")
                score += 30
            elif curr.overall_risk_level == "HIGH":
                drivers.append("Current risk level is HIGH")
                score += 20

        # D. Compliance
        if comp_history:
            latest_comp = comp_history[-1]
            evidence["compliance_status"] = latest_comp.overall_status
            if latest_comp.overall_status == "FAIL":
                drivers.append("Recent compliance assessment FAILED")
                score += 25
            elif latest_comp.overall_status == "REVIEW":
                drivers.append("Recent compliance assessment requires REVIEW")
                score += 10

        # E. Financial Implementation Mismatch
        if latest_prog_pct is not None and latest_exp_val is not None and sanc_amount and sanc_amount > 0:
            burn_rate = (latest_exp_val / sanc_amount) * 100
            evidence["analytical_progress_proxy"] = latest_prog_pct
            evidence["expenditure_ratio"] = round(burn_rate, 1)
            
            if burn_rate > 80 and latest_prog_pct < 40:
                drivers.append("High financial implementation combined with low analytical progress")
                score += 35
            elif burn_rate > 70 and latest_prog_pct < 60:
                drivers.append("Financial implementation is disproportionately high relative to progress")
                score += 20

        # 3. Calculate Confidence
        extracted_features = len(evidence)
        if extracted_features >= 5:
            confidence = "HIGH"
            coverage_pct = 95.0
        elif extracted_features >= 3:
            confidence = "MEDIUM"
            coverage_pct = 75.0
        else:
            confidence = "LOW"
            coverage_pct = 40.0

        if len(missing_data) > 0:
            confidence = "LOW"
            coverage_pct = max(30.0, coverage_pct - 30.0)

        # 4. Final Bucket
        if score >= 80:
            risk_level = "CRITICAL"
        elif score >= 60:
            risk_level = "HIGH"
        elif score >= 30:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"
            if not drivers:
                drivers.append("Project indicators are stable with no major completion delay signals")

        return {
            "status": "ASSESSABLE",
            "risk_level": risk_level,
            "risk_score": min(score, 100),
            "confidence": confidence,
            "coverage_pct": coverage_pct,
            "drivers": drivers,
            "evidence": evidence,
            "missing_data": missing_data,
            "provenance": "AI ASSESSMENT",
            "engine_version": self.engine_version
        }

    def _not_assessable(self, reason: str, missing: list = None) -> dict:
        return {
            "status": "NOT_ASSESSABLE",
            "risk_level": None,
            "risk_score": None,
            "confidence": None,
            "coverage_pct": 35.0,
            "drivers": [reason],
            "evidence": {},
            "missing_data": missing or [],
            "provenance": "AI ASSESSMENT",
            "engine_version": self.engine_version
        }
