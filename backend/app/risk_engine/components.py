import pandas as pd
import numpy as np
from datetime import date
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.ensemble import IsolationForest
from typing import List, Dict, Any, Optional

class PeerBenchmarkEngine:
    def get_peer_stats(self, df_projects: pd.DataFrame, category: str, exclude_id: int = None) -> Dict:
        if df_projects is None or df_projects.empty or 'category' not in df_projects.columns or 'sanctioned_amount' not in df_projects.columns:
            return {"median": 0.0, "mad": 0.0, "count": 0}
            
        peers = df_projects[df_projects['category'] == category]
        if exclude_id is not None and 'id' in peers.columns:
            peers = peers[peers['id'] != exclude_id]
            
        if len(peers) == 0:
            return {"median": 0.0, "mad": 0.0, "count": 0}
            
        peers_valid = pd.to_numeric(peers['sanctioned_amount'], errors='coerce').dropna()
        if len(peers_valid) == 0:
            return {"median": 0.0, "mad": 0.0, "count": 0}
            
        median = float(peers_valid.median())
        mad = float((peers_valid - median).abs().median())
        return {"median": median, "mad": mad, "count": len(peers_valid)}

class CostAnomalyDetector:
    def __init__(self, benchmarker: PeerBenchmarkEngine):
        self.benchmarker = benchmarker

    def detect(self, project: Dict, df_projects: pd.DataFrame) -> Dict:
        base = {
            "indicator": "Cost Anomaly",
            "status": "NOT_ASSESSABLE",
            "severity": "NOT_AVAILABLE",
            "score": None,
            "confidence": None,
            "explanation": "Required data unavailable in official dataset.",
            "evidence": {},
            "data_provenance": "UNAVAILABLE"
        }
        if 'category' not in project:
            return base
            
        stats = self.benchmarker.get_peer_stats(df_projects, project['category'], exclude_id=project.get('id'))
        if stats['count'] == 0 or stats['median'] == 0:
            base['severity'] = 'INSUFFICIENT_DATA'
            base['explanation'] = "Insufficient peer data for benchmark."
            base['evidence'] = {"peer_count": stats['count']}
            return base
        
        cost = project.get('sanctioned_amount')
        if cost is None or pd.isna(cost) or float(cost) <= 0:
            return base

        try:
            cost = float(cost)
        except (ValueError, TypeError):
            return base

        median = stats['median']
        mad = stats['mad']
        
        deviation_pct = ((cost - median) / median) * 100
        z_score = (cost - median) / (mad * 1.4826) if mad > 0 else 0
        
        if z_score > 3 or deviation_pct > 50:
            severity = "HIGH"
            score = 30
        elif z_score > 2 or deviation_pct > 20:
            severity = "MEDIUM"
            score = 15
        else:
            severity = "NORMAL"
            score = 0
            
        confidence = min(stats['count'] / 50.0, 1.0)
        
        return {
            "indicator": "Cost Anomaly",
            "status": "ASSESSABLE",
            "severity": severity,
            "score": score,
            "confidence": round(confidence, 2),
            "explanation": f"Sanctioned amount is {deviation_pct:.1f}% above the comparable-work median." if deviation_pct > 0 else "Cost is aligned with peer median.",
            "evidence": {
                "observed_cost": cost,
                "peer_median": median,
                "peer_mad": mad,
                "robust_z_score": round(z_score, 2) if mad > 0 else None,
                "deviation_pct": round(deviation_pct, 1),
                "peer_count": stats['count']
            },
            "data_provenance": "DERIVED"
        }

class FinancialAnomalyDetector:
    def check_payment_mismatch(self, project: Dict) -> Dict:
        base = {
            "indicator": "Payment vs Progress",
            "status": "NOT_ASSESSABLE",
            "severity": "NOT_AVAILABLE",
            "score": None,
            "confidence": None,
            "explanation": "Required data unavailable in official dataset.",
            "evidence": {},
            "data_provenance": "UNAVAILABLE"
        }
        
        sanctioned = project.get('sanctioned_amount')
        expenditure = project.get('expenditure')
        progress_pct = project.get('progress_pct')
        
        if sanctioned is None or pd.isna(sanctioned) or float(sanctioned) <= 0:
            return base
            
        if expenditure is None or pd.isna(expenditure):
            return base
            
        if progress_pct is None or pd.isna(progress_pct):
            return base
            
        sanctioned = float(sanctioned)
        expenditure = float(expenditure)
        progress_pct = float(progress_pct)
        
        exp_pct = (expenditure / sanctioned) * 100
        
        if exp_pct > 100:
            return {
                "indicator": "Payment vs Progress",
                "status": "ASSESSABLE",
                "severity": "HIGH",
                "score": 25,
                "confidence": 1.0,
                "explanation": f"Expenditure ({exp_pct:.1f}%) exceeds sanctioned amount.",
                "evidence": {
                    "expenditure_pct": round(exp_pct, 1),
                    "progress_pct": progress_pct
                },
                "data_provenance": "DERIVED"
            }
            
        mismatch = exp_pct - progress_pct
        
        if mismatch > 30:
            severity = "HIGH"
            score = 25
        elif mismatch > 15:
            severity = "MEDIUM"
            score = 10
        else:
            severity = "NORMAL"
            score = 0
            
        return {
            "indicator": "Payment vs Progress",
            "status": "ASSESSABLE",
            "severity": severity,
            "score": score,
            "confidence": 0.9,
            "explanation": f"Expenditure is {mismatch:.1f} percentage points ahead of analytical progress proxy." if mismatch > 0 else "Expenditure is aligned with progress proxy.",
            "evidence": {
                "expenditure_pct": round(exp_pct, 1),
                "progress_proxy_pct": progress_pct,
                "mismatch": round(mismatch, 1)
            },
            "data_provenance": "DERIVED"
        }

class TemporalAnomalyDetector:
    def check_delay(self, project: Dict, today: date = None) -> Dict:
        base = {
            "indicator": "Timeline & Delay",
            "status": "NOT_ASSESSABLE",
            "severity": "NOT_AVAILABLE",
            "score": None,
            "confidence": None,
            "explanation": "Required data unavailable in official dataset.",
            "evidence": {},
            "data_provenance": "UNAVAILABLE"
        }
        
        planned = project.get('planned_completion')
        actual = project.get('actual_completion')
        status = project.get('status')
        
        if not planned:
            return base
            
        if today is None:
            today = date.today()
            
        if status == 'COMPLETED':
            if not actual:
                base['status'] = 'NOT_ASSESSABLE'
                base['explanation'] = "Completed status with missing actual completion date."
                return base
            end_date = actual
        else:
            end_date = today
             
        delay_days = (end_date - planned).days
        
        if delay_days <= 0:
            return {
                "indicator": "Timeline & Delay",
                "status": "ASSESSABLE",
                "severity": "NORMAL",
                "score": 0,
                "confidence": 1.0,
                "explanation": "Project is on track or completed early.",
                "evidence": {"delay_days": delay_days},
                "data_provenance": "DERIVED"
            }
            
        if delay_days > 90:
            severity = "HIGH"
            score = 20
        elif delay_days > 30:
            severity = "MEDIUM"
            score = 10
        else:
            severity = "NORMAL"
            score = 0
            
        return {
            "indicator": "Timeline & Delay",
            "status": "ASSESSABLE",
            "severity": severity,
            "score": score,
            "confidence": 1.0,
            "explanation": f"Project is {delay_days} days overdue.",
            "evidence": {"delay_days": delay_days},
            "data_provenance": "DERIVED"
        }

class DuplicateDetector:
    def detect(self, target_project: Dict, df_projects: pd.DataFrame) -> Dict:
        base = {
            "indicator": "Duplicate Detection",
            "status": "NOT_ASSESSABLE",
            "severity": "NOT_AVAILABLE",
            "score": None,
            "confidence": None,
            "explanation": "Required data unavailable in official dataset.",
            "evidence": {},
            "data_provenance": "UNAVAILABLE"
        }
        
        if df_projects is None or df_projects.empty or 'category' not in df_projects.columns or 'id' not in df_projects.columns:
            return base
            
        if 'category' not in target_project or 'id' not in target_project:
            return base
            
        peers = df_projects[(df_projects['category'] == target_project['category']) & (df_projects['id'] != target_project['id'])].copy()
        if len(peers) == 0:
            base['explanation'] = "Insufficient peer data for similarity search."
            return base
            
        def make_text(p):
            parts = []
            if pd.notna(p.get('description')): parts.append(str(p['description']))
            if pd.notna(p.get('work_category')): parts.append(str(p['work_category']))
            if pd.notna(p.get('district')): parts.append(str(p['district']))
            if pd.notna(p.get('constituency')): parts.append(str(p['constituency']))
            return " ".join(parts).strip()
            
        corpus = [make_text(row) for _, row in peers.iterrows()] + [make_text(target_project)]
        if not any(corpus):
             return base
             
        vectorizer = TfidfVectorizer()
        try:
            tfidf = vectorizer.fit_transform(corpus)
            sims = cosine_similarity(tfidf[-1:], tfidf[:-1])[0]
            max_sim_idx = np.argmax(sims)
            max_sim = sims[max_sim_idx]
            
            matched_project_id = peers.iloc[max_sim_idx]['id'] if max_sim > 0 else None
            matched_project = peers.iloc[max_sim_idx] if max_sim > 0 else None
            
            signals = []
            score = 0
            if max_sim > 0.6:
                signals.append(f"Text similarity: {max_sim*100:.0f}%")
                
                c1 = target_project.get('sanctioned_amount', 0)
                c2 = matched_project.get('sanctioned_amount', 0) if matched_project is not None else 0
                if c1 and c2:
                    try:
                        c1 = float(c1)
                        c2 = float(c2)
                        if (abs(c1 - c2) / max(c1, c2)) < 0.1:
                            signals.append("Highly similar cost")
                            max_sim += 0.1
                    except (ValueError, TypeError):
                        pass
                        
                lat1, lon1 = target_project.get('latitude'), target_project.get('longitude')
                if matched_project is not None:
                    lat2, lon2 = matched_project.get('latitude'), matched_project.get('longitude')
                else:
                    lat2, lon2 = None, None
                    
                if pd.notna(lat1) and pd.notna(lon1) and pd.notna(lat2) and pd.notna(lon2):
                    try:
                        dist = np.sqrt((float(lat1)-float(lat2))**2 + (float(lon1)-float(lon2))**2)
                        if dist < 0.01:
                            signals.append("Very close geographic proximity")
                            max_sim += 0.1
                    except (ValueError, TypeError):
                        pass
                    
            if max_sim > 0.8:
                severity = "HIGH"
                score = 15
                reason = "Potential similar work found."
            elif max_sim > 0.6:
                severity = "MEDIUM"
                score = 8
                reason = "Similar description found."
            else:
                severity = "NORMAL"
                score = 0
                reason = "No duplicates detected."
                
            return {
                "indicator": "Duplicate Detection",
                "status": "ASSESSABLE",
                "severity": severity,
                "score": score,
                "confidence": 0.85,
                "explanation": reason,
                "evidence": {
                    "max_similarity": round(float(max_sim), 2),
                    "matched_project": int(matched_project_id) if matched_project_id else None,
                    "signals": signals,
                    "context": {"matched_mp": str(matched_project.get('mp_name')) if matched_project is not None else None}
                },
                "data_provenance": "AI ASSESSMENT"
            }
        except ValueError:
            return base

class VendorRiskAnalyzer:
    def analyze(self, target_contractors: List[int], df_contractor_projects: pd.DataFrame) -> Dict:
        base = {
            "indicator": "Vendor Risk",
            "status": "NOT_ASSESSABLE",
            "severity": "NOT_AVAILABLE",
            "score": None,
            "confidence": None,
            "explanation": "Required data unavailable in official dataset.",
            "evidence": {},
            "data_provenance": "UNAVAILABLE"
        }
        
        if not target_contractors or df_contractor_projects is None or df_contractor_projects.empty or 'contractor_id' not in df_contractor_projects.columns:
            return base
            
        counts = df_contractor_projects['contractor_id'].value_counts()
        has_amount = 'sanctioned_amount' in df_contractor_projects.columns
        
        max_count = 0
        total_val = 0.0
        
        for c in target_contractors:
            c_count = counts.get(c, 0)
            max_count = max(max_count, c_count)
            if has_amount:
                c_val_series = pd.to_numeric(df_contractor_projects[df_contractor_projects['contractor_id'] == c]['sanctioned_amount'], errors='coerce').fillna(0)
                c_val = c_val_series.sum()
                total_val = max(total_val, c_val)
        
        severity = "NORMAL"
        score = 0
        reasons = []
        
        if max_count > 10:
            severity = "HIGH"
            score = 5
            reasons.append(f"Vendor concentration: Contractor is associated with {max_count} active projects.")
        elif max_count > 5:
            severity = "MEDIUM"
            score = 3
            reasons.append(f"Vendor concentration risk: Contractor is associated with {max_count} projects.")
        else:
            reasons.append("Normal vendor distribution.")
            
        if has_amount and total_val > 100_000_000:
            if severity == "NORMAL": 
                severity = "MEDIUM"
                score = max(score, 3)
            reasons.append("High financial concentration with this vendor.")
            
        return {
            "indicator": "Vendor Risk",
            "status": "ASSESSABLE",
            "severity": severity,
            "score": score,
            "confidence": 1.0,
            "explanation": " | ".join(reasons),
            "evidence": {
                "max_project_count": int(max_count),
                "total_value": float(total_val) if has_amount else None
            },
            "data_provenance": "DERIVED"
        }

class IsolationForestDetector:
    def __init__(self):
        self._cached_preds = {}
        self._cached_df_key = None

    def detect(self, df_projects: pd.DataFrame, target_id: int) -> Dict:
        base = {
            "indicator": "Multivariate Anomaly (IF)",
            "status": "NOT_ASSESSABLE",
            "severity": "NOT_AVAILABLE",
            "score": None,
            "confidence": None,
            "explanation": "Required data unavailable in official dataset.",
            "evidence": {},
            "data_provenance": "UNAVAILABLE"
        }
        
        if df_projects is None or df_projects.empty or 'id' not in df_projects.columns:
            return base
            
        features = ['sanctioned_amount', 'progress_pct']
        available_features = []
        
        for f in features + ['expenditure_pct', 'delay_days']:
            # A column is not evidence merely because it exists.  Retain only
            # observed features with enough non-null official values.
            if f in df_projects.columns and pd.to_numeric(df_projects[f], errors='coerce').notna().sum() >= 10:
                available_features.append(f)
                
        if len(available_features) < 2:
            base['explanation'] = "Insufficient feature space for multivariate analysis."
            return base
            
        df_clean = df_projects[['id'] + available_features].copy()
        for f in available_features:
            df_clean[f] = pd.to_numeric(df_clean[f], errors='coerce')
        df_clean = df_clean.dropna(subset=available_features)
            
        if len(df_clean) < 10: 
            base['explanation'] = "Insufficient peer data for model training (n < 10)."
            return base
            
        current_key = (id(df_projects), len(df_projects))
        if self._cached_df_key != current_key:
            try:
                model = IsolationForest(contamination=0.1, random_state=42)
                raw_preds = model.fit_predict(df_clean[available_features])
                self._cached_preds = dict(zip(df_clean['id'], raw_preds))
                self._cached_df_key = current_key
            except Exception:
                base['status'] = 'NOT_ASSESSABLE'
                base['explanation'] = "Algorithm execution failed due to data shape."
                return base
        
        # Missing official values must result in UNAVAILABLE, never a zero-filled
        # synthetic observation.
        if target_id not in self._cached_preds:
            base['explanation'] = "Target lacks the observed feature set required for multivariate analysis."
            return base
            
        is_anomaly = self._cached_preds[target_id] == -1
        if is_anomaly:
            return {
                "indicator": "Multivariate Anomaly (IF)",
                "status": "ASSESSABLE",
                "severity": "MEDIUM",
                "score": 5,
                "confidence": 0.8,
                "explanation": "Potential statistical anomaly detected across multivariate project dimensions.",
                "evidence": {
                    "features_used": available_features,
                    "algorithm": "IsolationForest",
                    "contamination": 0.1,
                    "is_anomaly": True
                },
                "data_provenance": "AI ASSESSMENT"
            }
            
        return {
            "indicator": "Multivariate Anomaly (IF)",
            "status": "ASSESSABLE",
            "severity": "NORMAL",
            "score": 0,
            "confidence": 0.9,
            "explanation": "Consistent with multivariate peer distribution.",
            "evidence": {
                "features_used": available_features,
                "is_anomaly": False
            },
            "data_provenance": "AI ASSESSMENT"
        }
