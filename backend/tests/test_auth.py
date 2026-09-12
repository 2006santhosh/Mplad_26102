import os
os.environ["JWT_SECRET_KEY"] = "test_secret_for_pytest"

import pytest
import jwt
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from app.main import app
from app.auth_utils import create_access_token, decode_access_token, get_jwt_secret
from app.database import Base, get_db
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
from app.models import User, Project

test_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

from app.auth_utils import get_current_user
app.dependency_overrides.pop(get_current_user, None)
client = TestClient(app)

@pytest.fixture(scope="module")
def setup_db():
    Base.metadata.create_all(bind=test_engine)
    db = TestingSessionLocal()
    # Add a test user
    import bcrypt
    def get_hash(password: str):
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    if not db.query(User).filter(User.username == "test_admin").first():
        db.add(User(username="test_admin", role="Admin", password_hash=get_hash("password123")))
    if not db.query(User).filter(User.username == "test_viewer").first():
        db.add(User(username="test_viewer", role="UnknownRole", password_hash=get_hash("password123")))
    
    from app.models import MP, DataSource
    if not db.query(DataSource).filter(DataSource.id == 999).first():
        db.add(DataSource(id=999, source_name="Test DS", source_type="OFFICIAL"))
    if not db.query(MP).filter(MP.id == 999).first():
        db.add(MP(id=999, data_source_id=999, name="Test MP", state="Test State", status="Test", tenure="2024", allocated_amount=1.0))
    if not db.query(Project).filter(Project.id == 999).first():
        db.add(Project(id=999, mp_id=999, data_source_id=999, category="Roads", sanctioned_amount=1000000, location="TestLoc"))
        
    db.commit()
    yield db
    db.close()

def test_login_success(setup_db):
    response = client.post("/auth/login", json={"username": "test_admin", "password": "password123"})
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["role"] == "Admin"
    
    token = data["access_token"]
    payload = decode_access_token(token)
    assert payload["sub"] == "test_admin"
    assert payload["role"] == "Admin"
    assert "iat" in payload
    assert "exp" in payload

def test_login_invalid_password(setup_db):
    response = client.post("/auth/login", json={"username": "test_admin", "password": "wrongpassword"})
    assert response.status_code == 401

def test_login_nonexistent_user(setup_db):
    response = client.post("/auth/login", json={"username": "nobody", "password": "password123"})
    assert response.status_code == 401

def test_missing_auth_header():
    response = client.get("/api/dashboard/stats")
    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}

def test_malformed_token():
    response = client.get("/api/dashboard/stats", headers={"Authorization": "Bearer not.a.real.token"})
    assert response.status_code == 401
    assert "Invalid token" in response.json()["detail"] or "Not authenticated" in response.json()["detail"] or "decode" in response.json()["detail"].lower() or "signature" in response.json()["detail"].lower() or "token" in response.json()["detail"].lower()

def test_invalid_signature():
    payload = {"sub": "test_admin", "role": "Admin", "iat": datetime.utcnow(), "exp": datetime.utcnow() + timedelta(hours=1)}
    token = jwt.encode(payload, "wrong_secret", algorithm="HS256")
    response = client.get("/api/dashboard/stats", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401

def test_expired_token():
    past_time = datetime.utcnow() - timedelta(hours=1)
    payload = {"sub": "test_admin", "role": "Admin", "iat": past_time, "exp": past_time}
    token = jwt.encode(payload, get_jwt_secret(), algorithm="HS256")
    response = client.get("/api/dashboard/stats", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401

def test_missing_claims():
    payload = {"sub": "test_admin"} # missing role
    token = jwt.encode(payload, get_jwt_secret(), algorithm="HS256")
    response = client.get("/api/dashboard/stats", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401

def test_authenticated_read_success(setup_db):
    token = create_access_token({"sub": "test_admin", "role": "Admin"})
    response = client.get("/api/projects", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200

def test_rbac_authorized_action(setup_db):
    token = create_access_token({"sub": "test_admin", "role": "Admin"})
    response = client.post(
        "/api/projects/999/review/",
        json={"action": "COMMENT", "comment": "Test review", "reviewed_by": "Fake Identity"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["reviewed_by"] == "test_admin"  # Server ignores client field and uses JWT sub

def test_rbac_unauthorized_action(setup_db):
    token = create_access_token({"sub": "test_viewer", "role": "UnknownRole"})
    response = client.post(
        "/api/projects/999/review/",
        json={"action": "COMMENT", "comment": "Test review", "reviewed_by": "Fake Identity"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403
    assert response.json() == {"detail": "Insufficient role"}

def test_public_login():
    response = client.get("/docs") # public
    assert response.status_code == 200


def setup_module():
    app.dependency_overrides[get_db] = override_get_db
def teardown_module():
    app.dependency_overrides.clear()
