import pytest
from app.main import app
import pandas as pd
from datetime import date, timedelta
from app.risk_engine.components import (
    PeerBenchmarkEngine,
    CostAnomalyDetector,
    FinancialAnomalyDetector,
    TemporalAnomalyDetector,
    DuplicateDetector,
    VendorRiskAnalyzer,
    IsolationForestDetector
)
from app.risk_engine.aggregator import RiskAggregator

def test_cost_anomaly_normal():
    df = pd.DataFrame([
        {'id': 1, 'category': 'Road', 'sanctioned_amount': 100},
        {'id': 2, 'category': 'Road', 'sanctioned_amount': 105},
        {'id': 3, 'category': 'Road', 'sanctioned_amount': 95},
    ])
    project = {'id': 4, 'category': 'Road', 'sanctioned_amount': 102}
    
    detector = CostAnomalyDetector(PeerBenchmarkEngine())
    res = detector.detect(project, df)
    assert res['severity'] == 'NORMAL'
    assert res['evidence']['peer_median'] == 100.0 # median of [100, 105, 95] is 100

def test_cost_anomaly_exclude_target():
    # Target project is inside the df_projects
    df = pd.DataFrame([
        {'id': 1, 'category': 'Road', 'sanctioned_amount': 100},
        {'id': 2, 'category': 'Road', 'sanctioned_amount': 105},
        {'id': 3, 'category': 'Road', 'sanctioned_amount': 95},
        {'id': 4, 'category': 'Road', 'sanctioned_amount': 1000}, # outlier target
    ])
    project = {'id': 4, 'category': 'Road', 'sanctioned_amount': 1000}
    detector = CostAnomalyDetector(PeerBenchmarkEngine())
    res = detector.detect(project, df)
    assert res['severity'] == 'HIGH'
    assert res['evidence']['peer_median'] == 100.0 # target was excluded

def test_cost_anomaly_missing_data():
    df = pd.DataFrame()
    project = {'id': 2, 'category': 'Road'}
    detector = CostAnomalyDetector(PeerBenchmarkEngine())
    res = detector.detect(project, df)
    assert res['severity'] in ['INSUFFICIENT_DATA', 'NOT_AVAILABLE']

def test_rule_engine_payment_mismatch():
    engine = FinancialAnomalyDetector()
    res = engine.check_payment_mismatch({'expenditure': 50, 'sanctioned_amount': 100, 'progress_pct': 10})
    assert res['severity'] == 'HIGH'

def test_rule_engine_invalid_data():
    engine = FinancialAnomalyDetector()
    res1 = engine.check_payment_mismatch({'expenditure': None, 'sanctioned_amount': 100, 'progress_pct': 10})
    assert res1['severity'] == 'NOT_AVAILABLE'
    res2 = engine.check_payment_mismatch({'expenditure': 150, 'sanctioned_amount': 100, 'progress_pct': 100})
    assert res2['severity'] == 'HIGH' # exceeds sanctioned
    assert 'exceeds' in res2['explanation']

def test_rule_engine_delay():
    engine = TemporalAnomalyDetector()
    planned = date.today() - timedelta(days=100)
    res = engine.check_delay({'planned_completion': planned, 'actual_completion': None, 'status': 'ONGOING'})
    assert res['severity'] == 'HIGH'

def test_rule_engine_completed_missing_actual():
    engine = TemporalAnomalyDetector()
    planned = date.today() - timedelta(days=100)
    res = engine.check_delay({'planned_completion': planned, 'actual_completion': None, 'status': 'COMPLETED'})
    assert res['status'] == 'NOT_ASSESSABLE'
    assert 'missing actual' in res['explanation']

def test_duplicate_detector_valid():
    df = pd.DataFrame([
        {'id': 1, 'category': 'Road', 'district': 'D1', 'description': 'Repair', 'latitude': 10.0, 'longitude': 10.0},
    ])
    project = {'id': 2, 'category': 'Road', 'district': 'D1', 'description': 'Repair', 'latitude': 10.0, 'longitude': 10.0}
    detector = DuplicateDetector()
    res = detector.detect(project, df)
    assert res['severity'] == 'HIGH'
    assert 'Very close geographic proximity' in "".join(res['evidence'].get('signals', []))

def test_duplicate_detector_missing_coords():
    df = pd.DataFrame([
        {'id': 1, 'category': 'Road', 'district': 'D1', 'description': 'Repair'},
    ])
    project = {'id': 2, 'category': 'Road', 'district': 'D1', 'description': 'Repair'}
    detector = DuplicateDetector()
    res = detector.detect(project, df)
    assert res['severity'] == 'HIGH'
    assert 'geographic proximity' not in "".join(res['evidence'].get('signals', []))

def test_vendor_concentration_value():
    df = pd.DataFrame([
        {'contractor_id': 1, 'sanctioned_amount': 50000000},
        {'contractor_id': 1, 'sanctioned_amount': 60000000}
    ])
    detector = VendorRiskAnalyzer()
    res = detector.analyze([1], df)
    # count is 2 (NORMAL), but value is 11 Cr. > 10 Cr is MEDIUM.
    assert res['severity'] == 'MEDIUM'
    assert res['evidence']['total_value'] == 110000000

def test_iso_forest_empty():
    df = pd.DataFrame()
    detector = IsolationForestDetector()
    res = detector.detect(df, 1)
    assert res['status'] == 'NOT_ASSESSABLE'

def test_risk_aggregation_empty_df():
    aggregator = RiskAggregator()
    project = {
        'id': 1, 'category': 'Road', 'sanctioned_amount': 100, 'expenditure': 50, 
        'progress_pct': 50, 'planned_completion': date.today(), 'actual_completion': None,
        'status': 'ONGOING', 'location': 'A', 'description': 'B', 'contractors': []
    }
    context = {'df_projects': pd.DataFrame(), 'df_contractor_projects': pd.DataFrame()}
    
    res = aggregator.calculate_risk(project, context)
    # Financial and Temporal anomaly detectors will evaluate to ASSESSABLE, giving count >= 2. So it returns LOW rather than LIMITED.
    assert res['score'] == 0
    assert res['level'] == 'LOW'


def teardown_module():
    app.dependency_overrides.clear()
