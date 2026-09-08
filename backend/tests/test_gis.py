from fastapi.testclient import TestClient
from app.main import app
from app.database import get_db
from app.auth_utils import get_current_user
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
from app.models import Base, Project, DataSource

engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

def override_get_db():
    db = TestingSessionLocal()
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
    
    # Add a mock official data source
    ds = DataSource(id=1, source_type="OFFICIAL", source_name="Test Source")
    db.add(ds)
    
    # Valid nearby projects (Should cluster together)
    p1 = Project(id=1, mp_id=1, data_source_id=1, latitude=10.12, longitude=20.12, sanctioned_amount=100)
    p2 = Project(id=2, mp_id=1, data_source_id=1, latitude=10.14, longitude=20.14, sanctioned_amount=200)
    
    # Valid distant project (Different cluster)
    p3 = Project(id=3, mp_id=1, data_source_id=1, latitude=50.12, longitude=60.12, sanctioned_amount=300)
    
    # Missing lat/lng
    p4 = Project(id=4, mp_id=1, data_source_id=1, latitude=None, longitude=None)
    
    # Invalid lat/lng
    p5 = Project(id=5, mp_id=1, data_source_id=1, latitude=100.0, longitude=20.12) # lat > 90
    p6 = Project(id=6, mp_id=1, data_source_id=1, latitude=10.0, longitude=-200.0) # lng < -180
    # 0,0 coordinates
    p7 = Project(id=7, mp_id=1, data_source_id=1, latitude=0.0, longitude=0.0)
    
    db.add_all([p1, p2, p3, p4, p5, p6, p7])
    db.commit()
    db.close()

def test_gis_clusters():
    response = client.get("/api/gis/clusters")
    assert response.status_code == 200
    data = response.json()
    
    assert data["total_valid_projects"] == 3
    assert len(data["clusters"]) == 2
    
    cluster1 = data["clusters"][0]
    assert cluster1["project_count"] == 2 # p1, p2
    assert cluster1["total_amount"] == 300
    assert round(cluster1["center_latitude"], 2) == 10.13 # Average of 10.12 and 10.14
    assert round(cluster1["center_longitude"], 2) == 20.13 # Average of 20.12 and 20.14
    
    cluster2 = data["clusters"][1]
    assert cluster2["project_count"] == 1 # p3
    assert cluster2["center_latitude"] == 50.12


def teardown_module():
    app.dependency_overrides.clear()

from app.routers.gis import is_valid_coordinate

def test_is_valid_coordinate_invalid_string():
    assert is_valid_coordinate("invalid", "20.12") == False
    assert is_valid_coordinate("10.12", "invalid") == False
