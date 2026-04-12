"""Database setup and session helpers."""

import os
from typing import Generator

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:////app/data/cfs.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, _connection_record) -> None:
    """Apply SQLite pragmas for write concurrency and FK integrity."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Base declarative model class."""


def ensure_runtime_schema() -> None:
    """Apply lightweight runtime schema migrations for SQLite deployments."""
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if "spools" not in table_names:
        return

    existing = {col["name"] for col in inspector.get_columns("spools")}
    required = {
        "tare_weight_g": "FLOAT",
        "last_gross_weight_g": "FLOAT",
        "calibration_factor": "FLOAT",
        "calibrated_at": "DATETIME",
    }

    with engine.begin() as conn:
        for column_name, column_type in required.items():
            if column_name in existing:
                continue
            conn.execute(
                text(
                    f"ALTER TABLE spools ADD COLUMN {column_name} {column_type}"
                )
            )


def get_db() -> Generator[Session, None, None]:
    """Yield one SQLAlchemy session per request context."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
