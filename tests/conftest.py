"""Shared pytest fixtures for API and service tests."""

import pytest


@pytest.fixture(autouse=True)
def reset_db() -> None:
    """Reset database tables between tests.

    Returns:
    --------
        None:
            Clears persistent rows before each test.
    """
    from app.database import SessionLocal
    from app.models import PrintJob, Spool

    db = SessionLocal()
    try:
        db.query(PrintJob).delete()
        db.query(Spool).delete()
        db.commit()
    finally:
        db.close()
