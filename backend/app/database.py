import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "mplad.db")
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH}")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def database_diagnostic() -> dict:
    """Return a safe runtime identifier; never return credentials or query parameters."""
    if DATABASE_URL.startswith("sqlite:///"):
        return {"engine": "sqlite", "database": os.path.abspath(DATABASE_URL.removeprefix("sqlite:///"))}
    return {"engine": DATABASE_URL.split(":", 1)[0], "database": "configured externally"}

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
