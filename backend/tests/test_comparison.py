from fastapi.testclient import TestClient
from app.main import app
from app.database import get_db
from app.auth_utils import get_current_user
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
from app.models import DataSource, Base, Project
from datetime import datetime, date, timedelta

engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    if not db.query(DataSource).filter(DataSource.id == 1).first():
        db.add(DataSource(id=1, source_name="Official Data", source_type="OFFICIAL"))
        db.commit()
    try:
        yield db
    finally:
        db.close()

client = TestClient(app)

def setup_module():
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: {'sub': 'test', 'role': 'Admin'}
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    
    today = date.today()
    
    # 1. Target exactly +50% -> NOT anomaly
    p1 = Project(id=1, mp_id=1, data_source_id=1, category="Roads", sanctioned_amount=1500)
    peer1 = Project(id=10, mp_id=1, data_source_id=1, category="Roads", sanctioned_amount=1000)
    
    # 2. Target > +50% -> Anomaly
    p2 = Project(id=2, mp_id=1, data_source_id=1, category="Water", sanctioned_amount=1501)
    peer2 = Project(id=20, mp_id=1, data_source_id=1, category="Water", sanctioned_amount=1000)
    
    # 3. Target exactly -50% -> NOT anomaly
    p3 = Project(id=3, mp_id=1, data_source_id=1, category="Health", sanctioned_amount=500)
    peer3 = Project(id=30, mp_id=1, data_source_id=1, category="Health", sanctioned_amount=1000)
    
    # 4. Target < -50% -> Anomaly
    p4 = Project(id=4, mp_id=1, data_source_id=1, category="Edu", sanctioned_amount=499)
    peer4 = Project(id=40, mp_id=1, data_source_id=1, category="Edu", sanctioned_amount=1000)
    
    # 5. Missing category
    p5 = Project(id=5, mp_id=1, data_source_id=1, category=None, sanctioned_amount=1000)
    
    # 6. Invalid peer amount (-500) -> Excluded, leaves 0 peers
    p6 = Project(id=6, mp_id=1, data_source_id=1, category="InvalidPeer", sanctioned_amount=1000)
    peer6 = Project(id=60, mp_id=1, data_source_id=1, category="InvalidPeer", sanctioned_amount=-500)
    
    # 7. Missing target amount -> Excludes metric
    p7 = Project(id=7, mp_id=1, data_source_id=1, category="MissingTarget", sanctioned_amount=None, planned_start=today, planned_completion=today+timedelta(days=100))
    peer7 = Project(id=70, mp_id=1, data_source_id=1, category="MissingTarget", sanctioned_amount=1000, planned_start=today, planned_completion=today+timedelta(days=50))
    
    # 8. Zero peer average
    p8 = Project(id=8, mp_id=1, data_source_id=1, category="ZeroAvg", sanctioned_amount=1000)
    peer8 = Project(id=80, mp_id=1, data_source_id=1, category="ZeroAvg", sanctioned_amount=0)

    db.add_all([
        p1, peer1, p2, peer2, p3, peer3, p4, peer4, p5, p6, peer6, p7, peer7, p8, peer8
    ])
    db.commit()
    db.close()


def test_comparison_exactly_plus_50():
    response = client.get("/api/projects/1/comparison")
    data = response.json()
    assert data["metrics"][0]["difference_percentage"] == 50.0
    assert data["metrics"][0]["is_anomaly"] == False

def test_comparison_greater_than_plus_50():
    response = client.get("/api/projects/2/comparison")
    data = response.json()
    assert data["metrics"][0]["difference_percentage"] > 50.0
    assert data["metrics"][0]["is_anomaly"] == True

def test_comparison_exactly_minus_50():
    response = client.get("/api/projects/3/comparison")
    data = response.json()
    assert data["metrics"][0]["difference_percentage"] == -50.0
    assert data["metrics"][0]["is_anomaly"] == False

def test_comparison_less_than_minus_50():
    response = client.get("/api/projects/4/comparison")
    data = response.json()
    assert data["metrics"][0]["difference_percentage"] < -50.0
    assert data["metrics"][0]["is_anomaly"] == True

def test_comparison_missing_category():
    response = client.get("/api/projects/5/comparison")
    data = response.json()
    assert data["peer_count"] == 0
    assert len(data["metrics"]) == 0

def test_comparison_invalid_peer():
    response = client.get("/api/projects/6/comparison")
    data = response.json()
    # The invalid peer (-500) is excluded, so valid_peer_costs is empty, metric is not appended
    assert data["peer_count"] == 1 # Peer is found
    assert len(data["metrics"]) == 0 # But metric is empty

def test_comparison_missing_target_metric():
    response = client.get("/api/projects/7/comparison")
    data = response.json()
    # Target amount is missing, so Cost metric is skipped. Duration metric is appended.
    assert len(data["metrics"]) == 1
    assert data["metrics"][0]["metric_name"] == "Planned Duration (Days)"

def test_comparison_zero_peer_average():
    response = client.get("/api/projects/8/comparison")
    data = response.json()
    # Peer average is 0. Division by zero avoided. diff_pct is None.
    assert data["metrics"][0]["difference_percentage"] is None
    assert data["metrics"][0]["is_anomaly"] == False

def test_comparison_nonexistent():
    response = client.get("/api/projects/999/comparison")
    assert response.status_code == 404


def teardown_module():
    app.dependency_overrides.clear()
