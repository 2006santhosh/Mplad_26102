import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.database import Base, engine, get_db
from app import models, auth_utils
from app.risk_engine import geo_utils
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import datetime

TEST_SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(TEST_SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})

# --- Setup Isolation ---
def setup_module(module):
    Base.metadata.create_all(bind=test_engine)

def teardown_module(module):
    Base.metadata.drop_all(bind=test_engine)

@pytest.fixture
def db_session():
    connection = test_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()

@pytest.fixture
def auth_client(db_session):
    def override_get_db():
        yield db_session
        
    def override_get_current_user():
        return {"sub": "test_admin", "role": "Admin"}
        
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[auth_utils.get_current_user] = override_get_current_user
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()

@pytest.fixture
def unauth_client(db_session):
    def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()

def seed_geo_data(db: Session):
    ds_off = models.DataSource(source_name="Official", source_type="OFFICIAL", source_url="x")
    ds_syn = models.DataSource(source_name="Synthetic", source_type="SYNTHETIC", source_url="x")
    db.add_all([ds_off, ds_syn])
    db.flush()
    
    mp = models.MP(name="Test MP", constituency="Test", state="State", data_source_id=ds_off.id)
    db.add(mp)
    db.flush()

    # 1. Valid official project
    p1 = models.Project(
        mp_id=mp.id, data_source_id=ds_off.id, 
        latitude=20.0, longitude=85.0, gps_provenance="OFFICIAL",
        category="Roads", description="Build road in village A", status="ONGOING"
    )
    
    # 2. Invalid coordinate project
    p2 = models.Project(
        mp_id=mp.id, data_source_id=ds_off.id, 
        latitude=100.0, longitude=200.0, gps_provenance="OFFICIAL",
        category="Roads", description="Build road in village B", status="ONGOING"
    )
    
    # 3. Missing coordinates
    p3 = models.Project(
        mp_id=mp.id, data_source_id=ds_off.id, 
        latitude=None, longitude=None, gps_provenance="UNAVAILABLE",
        category="Water", description="Water tank", status="ONGOING"
    )
    
    # 4. Near duplicate to p1
    p4 = models.Project(
        mp_id=mp.id, data_source_id=ds_off.id, 
        latitude=20.001, longitude=85.001, gps_provenance="OFFICIAL",
        category="Roads", description="Build road in village A", status="ONGOING"
    )

    # 5. Nearby but NOT duplicate (different category)
    p5 = models.Project(
        mp_id=mp.id, data_source_id=ds_off.id, 
        latitude=20.001, longitude=85.002, gps_provenance="OFFICIAL",
        category="Health", description="Build clinic", status="ONGOING"
    )

    # 6. Synthetic data
    p6 = models.Project(
        mp_id=mp.id, data_source_id=ds_syn.id, 
        latitude=21.0, longitude=86.0, gps_provenance="SYNTHETIC",
        category="Health", description="Synthetic clinic", status="ONGOING"
    )
    
    db.add_all([p1, p2, p3, p4, p5, p6])
    db.commit()
    return p1, p2, p3, p4, p5, p6

# --- Unit Tests: Geo Utils ---
def test_geo_utils_validation():
    # Valid
    assert geo_utils.validate_coordinates(20.0, 85.0) == 'VALID'
    assert geo_utils.validate_coordinates(-90.0, 180.0) == 'VALID'
    
    # Invalid
    assert geo_utils.validate_coordinates(100.0, 85.0) == 'INVALID'
    assert geo_utils.validate_coordinates(20.0, 200.0) == 'INVALID'
    assert geo_utils.validate_coordinates("abc", "def") == 'INVALID'
    assert geo_utils.validate_coordinates(0.0, 0.0) == 'INVALID' # Placeholder
    
    # Missing
    assert geo_utils.validate_coordinates(None, None) == 'UNAVAILABLE'

def test_geo_utils_distance():
    # Haversine distance (~111km per degree of latitude)
    dist = geo_utils.calculate_distance_km(20.0, 85.0, 21.0, 85.0)
    assert 110 <= dist <= 112
    
    # Close distance
    dist2 = geo_utils.calculate_distance_km(20.0, 85.0, 20.001, 85.0)
    assert dist2 < 0.5  # Should be ~111 meters
    
    # Invalid points return None
    assert geo_utils.calculate_distance_km(100, 85, 20, 85) is None

# --- API Tests ---
def test_map_api(auth_client, db_session):
    seed_geo_data(db_session)
    response = auth_client.get("/api/projects/map")
    assert response.status_code == 200
    data = response.json()
    
    # There are 6 projects total, but only 4 have VALID coordinates (p1, p4, p5, p6)
    # The API returns ALL valid coordinates from all projects (including synthetic if queried normally, 
    # but wait! get_map_data currently queries all projects regardless of source_type).
    
    valid_ids = [p["project_id"] for p in data["projects"]]
    assert len(data["projects"]) == 4 
    assert data["unavailable_gps_count"] == 2 # p2 (invalid), p3 (missing)
    assert data["valid_gps_count"] == 4
    
    # Check coverage (4 / 6 * 100)
    assert abs(data["gps_coverage_percentage"] - 66.66) < 0.1

def test_early_warning_geo_rules(auth_client, db_session):
    p1, p2, p3, p4, p5, p6 = seed_geo_data(db_session)

    # 1. Coordinate Validation Issue — OFFICIAL provenance, invalid coords
    r2 = auth_client.post(f"/api/projects/{p2.id}/early-warnings/assess")
    assert r2.status_code == 200
    assert any(w["warning_type"] == "COORDINATE_VALIDATION_ISSUE" for w in r2.json()["warnings"]), \
        f"Expected COORDINATE_VALIDATION_ISSUE for p2, got: {[w['warning_type'] for w in r2.json()['warnings']]}"

    # 2. Near Duplicate Location (p1 vs p4 — same category, <0.5 km)
    r1 = auth_client.post(f"/api/projects/{p1.id}/early-warnings/assess")
    warnings1 = r1.json()["warnings"]
    assert any(w["warning_type"] == "NEAR_DUPLICATE_LOCATION" for w in warnings1), \
        f"Expected NEAR_DUPLICATE_LOCATION for p1, got: {[w['warning_type'] for w in warnings1]}"

    # 3. Nearby but NOT duplicate because different category (p5 is Health, p1/p4 are Roads)
    r5 = auth_client.post(f"/api/projects/{p5.id}/early-warnings/assess")
    warnings5 = r5.json()["warnings"]
    assert not any(w["warning_type"] == "NEAR_DUPLICATE_LOCATION" for w in warnings5), \
        "NEAR_DUPLICATE_LOCATION must not fire for different categories"

    # 4. Missing GPS (UNAVAILABLE) — no geo warnings
    r3 = auth_client.post(f"/api/projects/{p3.id}/early-warnings/assess")
    warnings3 = r3.json()["warnings"]
    geo_types = {"COORDINATE_VALIDATION_ISSUE", "NEAR_DUPLICATE_LOCATION", "SPATIAL_CLUSTER"}
    assert not any(w["warning_type"] in geo_types for w in warnings3), \
        "Missing GPS project must not receive geo warnings"

    # 5. SYNTHETIC provenance project — must NOT trigger COORDINATE_VALIDATION_ISSUE
    #    (p6 has valid-range synthetic coords; the engine requires OFFICIAL provenance)
    r6 = auth_client.post(f"/api/projects/{p6.id}/early-warnings/assess")
    warnings6 = r6.json()["warnings"]
    assert not any(w["warning_type"] == "COORDINATE_VALIDATION_ISSUE" for w in warnings6), \
        "SYNTHETIC provenance must not trigger COORDINATE_VALIDATION_ISSUE"

def test_dashboard_gps_coverage(auth_client, db_session):
    seed_geo_data(db_session)
    # The dashboard only queries OFFICIAL projects usually, but let's see what it returns
    r = auth_client.get("/api/dashboard/stats")
    assert r.status_code == 200
    stats = r.json()
    assert "gps_coverage_percentage" in stats
    
    # Let's see: The dashboard filters for Official.
    # Official projects: p1(valid), p2(invalid), p3(missing), p4(valid), p5(valid). Total 5.
    # Valid = 3 (p1, p4, p5)
    # Coverage = 3/5 = 60%
    assert abs(stats["gps_coverage_percentage"] - 60.0) < 0.1

def test_map_rbac(unauth_client):
    r = unauth_client.get("/api/projects/map")
    assert r.status_code == 401
