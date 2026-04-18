"""SQLAlchemy engine, session und Basisklasse."""
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import settings

# Sicherstellen dass das Data-Verzeichnis existiert (für SQLite-File)
if settings.database_url.startswith("sqlite"):
    db_path = settings.database_url.split("sqlite:///")[-1]
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
