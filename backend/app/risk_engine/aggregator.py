from typing import Dict, List, Any
from .components import (
    PeerBenchmarkEngine, 
    CostAnomalyDetector, 
    FinancialAnomalyDetector, 
    TemporalAnomalyDetector,
    DuplicateDetector, 
    VendorRiskAnalyzer,
    IsolationForestDetector
)

class RiskAggregator:
    def __init__(self):
        self.benchmarker = PeerBenchmarkEngine()
        self.cost_detector = CostAnomalyDetector(self.benchmarker)
        self.fin_detector = FinancialAnomalyDetector()
        self.time_detector = TemporalAnomalyDetector()
        self.duplicate_detector = DuplicateDetector()
        self.vendor_analyzer = VendorRiskAnalyzer()
        self.iso_forest = IsolationForestDetector()

    def calculate_risk(self, target_project: Dict, context_data: Dict) -> Dict:
        indicators = []
        if not isinstance(context_data, dict):
            context_data = {}
            
        df_projects = context_data.get('df_projects')
        
        indicators.append(self.cost_detector.detect(target_project, df_projects))
        indicators.append(self.fin_detector.check_payment_mismatch(target_project))
        indicators.append(self.time_detector.check_delay(target_project))
        indicators.append(self.duplicate_detector.detect(target_project, df_projects))
        indicators.append(self.vendor_analyzer.analyze(target_project.get('contractors', []), context_data.get('df_contractor_projects')))
        indicators.append(self.iso_forest.detect(df_projects, target_project.get('id')))
        
        assessable = [ind for ind in indicators if ind.get("status") == "ASSESSABLE"]
        assessable_count = len(assessable)
        total_count = len(indicators)
        
        coverage_pct = (assessable_count / total_count * 100) if total_count > 0 else 0
        
        assessment_coverage = {
            "assessable": assessable_count,
            "total": total_count,
            "percentage": round(coverage_pct, 1)
        }
        
        if assessable_count < 2:
            assessment_status = "LIMITED / INSUFFICIENT_EVIDENCE"
            level = "LIMITED"
            score = None
        else:
            assessment_status = "COMPLETION"
            raw_score = sum((ind.get('score') or 0) for ind in assessable)
            score = min(raw_score, 100)
            
            if score >= 60:
                level = "CRITICAL"
            elif score >= 40:
                level = "HIGH"
            elif score >= 20:
                level = "MEDIUM"
            else:
                level = "LOW"
                
        reasons = []
        for ind in indicators:
            if ind.get("severity") in ["HIGH", "MEDIUM"] and ind.get("status") == "ASSESSABLE":
                reasons.append(ind.get("explanation", "Anomalous pattern detected."))
                
        return {
            "score": score,
            "level": level,
            "assessment_status": assessment_status,
            "assessment_coverage": assessment_coverage,
            "assessable_indicator_count": assessable_count,
            "total_indicator_count": total_count,
            "risk_reasons": reasons,
            "indicators": indicators
        }
