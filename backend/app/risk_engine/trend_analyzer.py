from typing import List, Dict, Any

class TrendAnalyzer:
    def __init__(self):
        pass
        
    def analyze_risk_trend(self, assessments: List[Dict]) -> Dict:
        """
        Analyzes a chronological list of risk assessments (oldest to newest).
        """
        if not assessments or len(assessments) < 2:
            return {
                "status": "INSUFFICIENT_HISTORY",
                "explanation": "Historical trend unavailable — only one assessment recorded.",
                "score_change": None
            }
            
        recent = assessments[-3:] if len(assessments) >= 3 else assessments
        
        first = recent[0]
        last = recent[-1]
        
        s1 = first.get('risk_score')
        s_last = last.get('risk_score')
        
        if s1 is None or s_last is None:
            return {
                "status": "INSUFFICIENT_HISTORY",
                "explanation": "Historical scores are missing, cannot calculate trend.",
                "score_change": None
            }
            
        diff = s_last - s1
        
        c1 = first.get('assessment_coverage_pct', 0)
        c_last = last.get('assessment_coverage_pct', 0)
        coverage_diff = c_last - c1
        
        if diff > 10:
            status = "INCREASING"
        elif diff < -10:
            status = "DECREASING"
        elif abs(diff) <= 10:
            status = "STABLE"
        else:
            status = "VOLATILE"
            
        explanation = f"Risk score {'increased' if diff > 0 else 'decreased' if diff < 0 else 'remained stable'} "
        explanation += f"by {abs(diff)} points across the last {len(recent)} available assessments."
        
        if abs(coverage_diff) > 10:
            explanation += f" Assessment coverage also {'increased' if coverage_diff > 0 else 'decreased'} from {c1:.0f}% to {c_last:.0f}%."
            
        return {
            "status": status,
            "explanation": explanation,
            "score_change": diff
        }

    def analyze_indicator_trend(self, points: List[Dict]) -> Dict:
        """
        Analyzes a chronological list of indicator history points.
        """
        assessable = [p for p in points if p.get('status') == 'ASSESSABLE' and p.get('score') is not None]
        
        if len(assessable) < 2:
            return {
                "trend": "INSUFFICIENT_HISTORY",
                "explanation": "Not enough assessable historical observations."
            }
            
        recent = assessable[-3:]
        s1 = recent[0]['score']
        s_last = recent[-1]['score']
        diff = s_last - s1
        
        if diff > 5:
            trend = "INCREASING"
            expl = f"Score increased across the last {len(recent)} assessable observations."
        elif diff < -5:
            trend = "DECREASING"
            expl = f"Score decreased across the last {len(recent)} assessable observations."
        else:
            trend = "STABLE"
            expl = f"Score remained stable across the last {len(recent)} assessable observations."
            
        return {
            "trend": trend,
            "explanation": expl
        }
