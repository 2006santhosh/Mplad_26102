import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import bcrypt
from app.database import SessionLocal
from app.models import User

db = SessionLocal()

users_to_create = [
    {"username": "admin_demo",    "password": "demo123", "role": "Admin"},
    {"username": "auditor_demo",  "password": "demo123", "role": "Auditor"},
    {"username": "state_demo",    "password": "demo123", "role": "State"},
    {"username": "district_demo", "password": "demo123", "role": "District"},
]

for u in users_to_create:
    existing = db.query(User).filter(User.username == u["username"]).first()
    if not existing:
        pw_hash = bcrypt.hashpw(u["password"].encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        user = User(username=u["username"], role=u["role"], password_hash=pw_hash)
        db.add(user)
        print(f"Created: {u['username']} ({u['role']})")
    else:
        print(f"Already exists: {u['username']}")

db.commit()
db.close()
print("Done.")
