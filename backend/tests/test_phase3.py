import pytest
from app.risk_engine.components import CostAnomalyDetector, FinancialAnomalyDetector, TemporalAnomalyDetector, DuplicateDetector, PeerBenchmarkEngine, IsolationForestDetector, VendorRiskAnalyzer
from app.risk_engine.aggregator import RiskAggregator
import pandas as pd
from datetime import date

def test_cost_anomaly_missing_data():
    benchmarker = PeerBenchmarkEngine()
    detector = CostAnomalyDetector(benchmarker)
    project = {}
    df_projects = pd.DataFrame()
    res = detector.detect(project, df_projects)
    assert res['status'] == 'NOT_ASSESSABLE'
    assert res['severity'] == 'NOT_AVAILABLE'
    assert res['data_provenance'] == 'UNAVAILABLE'

def test_cost_anomaly_valid():
    benchmarker = PeerBenchmarkEngine()
    detector = CostAnomalyDetector(benchmarker)
    project = {'id': 1, 'category': 'A', 'sanctioned_amount': 2000}
    df_projects = pd.DataFrame([
        {'id': 2, 'category': 'A', 'sanctioned_amount': 1000},
        {'id': 3, 'category': 'A', 'sanctioned_amount': 1100},
        {'id': 4, 'category': 'A', 'sanctioned_amount': 900}
    ])
    res = detector.detect(project, df_projects)
    assert res['status'] == 'ASSESSABLE'
    assert res['severity'] == 'HIGH'
    assert res['score'] == 30
    assert res['data_provenance'] == 'DERIVED'

def test_financial_anomaly_missing_data():
    detector = FinancialAnomalyDetector()
    res = detector.check_payment_mismatch({})
    assert res['status'] == 'NOT_ASSESSABLE'
    
def test_financial_anomaly_high_mismatch():
    detector = FinancialAnomalyDetector()
    res = detector.check_payment_mismatch({'sanctioned_amount': 100, 'expenditure': 80, 'progress_pct': 40})
    assert res['status'] == 'ASSESSABLE'
    assert res['severity'] == 'HIGH'

def test_temporal_anomaly():
    detector = TemporalAnomalyDetector()
    today = date(2026, 1, 1)
    res = detector.check_delay({'planned_completion': date(2025, 1, 1), 'status': 'IN_PROGRESS'}, today=today)
    assert res['status'] == 'ASSESSABLE'
    assert res['severity'] == 'HIGH'

def test_aggregator_limited_evidence():
    aggregator = RiskAggregator()
    # Provide empty context to simulate missing data
    res = aggregator.calculate_risk({}, {})
    assert res['assessment_status'] == 'LIMITED / INSUFFICIENT_EVIDENCE'
    assert res['level'] == 'LIMITED'
    assert res['score'] is None
    assert res['assessable_indicator_count'] == 0

def test_aggregator_assessable():
    aggregator = RiskAggregator()
    project = {
        'id': 1, 
        'category': 'A', 
        'sanctioned_amount': 100, 
        'expenditure': 80, 
        'progress_pct': 40,
        'planned_completion': date(2025, 1, 1),
        'status': 'IN_PROGRESS'
    }
    df_projects = pd.DataFrame([
        {'id': 2, 'category': 'A', 'sanctioned_amount': 100, 'progress_pct': 40, 'expenditure_pct': 80, 'delay_days': 365},
    ])
    res = aggregator.calculate_risk(project, {'df_projects': df_projects})
    assert res['assessment_status'] == 'COMPLETION'
    assert res['assessable_indicator_count'] >= 2
    assert res['level'] in ['MEDIUM', 'HIGH', 'CRITICAL']
