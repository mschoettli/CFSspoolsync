"""Database setup and session helpers."""

from datetime import datetime, timezone
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
    with engine.begin() as conn:
        if "spools" in table_names:
            existing = {col["name"] for col in inspector.get_columns("spools")}
            required = {
                "tare_weight_g": "FLOAT",
                "last_gross_weight_g": "FLOAT",
                "calibration_factor": "FLOAT",
                "calibrated_at": "DATETIME",
            }
            for column_name, column_type in required.items():
                if column_name in existing:
                    continue
                conn.execute(
                    text(
                        f"ALTER TABLE spools ADD COLUMN {column_name} {column_type}"
                    )
                )

        if "tare_defaults" in table_names:
            defaults_columns = {
                col["name"] for col in inspector.get_columns("tare_defaults")
            }
            if "is_system" not in defaults_columns:
                conn.execute(
                    text(
                        "ALTER TABLE tare_defaults ADD COLUMN is_system BOOLEAN NOT NULL DEFAULT 1"
                    )
                )

            count = conn.execute(
                text("SELECT COUNT(*) FROM tare_defaults")
            ).scalar_one()
            if count == 0:
                from app.services.spool_defaults import STATIC_BRAND_TARE_DEFAULTS

                now = datetime.now(timezone.utc).replace(tzinfo=None)
                for item in STATIC_BRAND_TARE_DEFAULTS:
                    conn.execute(
                        text(
                            """
                            INSERT INTO tare_defaults
                                (brand_key, brand_label, tare_weight_g, is_system, updated_at)
                            VALUES
                                (:brand_key, :brand_label, :tare_weight_g, :is_system, :updated_at)
                            """
                        ),
                        {
                            "brand_key": item["brand_key"],
                            "brand_label": item["brand_label"],
                            "tare_weight_g": item["tare_weight_g"],
                            "is_system": 1,
                            "updated_at": now,
                        },
                    )


def get_db() -> Generator[Session, None, None]:
    """Yield one SQLAlchemy session per request context."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
