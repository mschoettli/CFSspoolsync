"""HTTP routes for print job history."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import PrintJob
from app.schemas.job import JobOut

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("", response_model=list[JobOut])
def list_jobs(limit: int = Query(30, le=100), db: Session = Depends(get_db)):
    """Return recent print jobs ordered by start date descending."""
    jobs = (
        db.query(PrintJob)
        .order_by(PrintJob.started_at.desc())
        .limit(limit)
        .all()
    )

    result = []
    running_seen = False
    for job in jobs:
        if job.status == "running":
            if running_seen:
                continue
            running_seen = True

        consumed = 0.0
        for letter in "abcd":
            before = getattr(job, f"slot_{letter}_before")
            after = getattr(job, f"slot_{letter}_after")
            if before is not None and after is not None:
                consumed += before - after

        duration_seconds = None
        if (
            job.status in {"finished", "cancelled", "error"}
            and job.started_at is not None
            and job.finished_at is not None
        ):
            duration_seconds = round(
                max(0.0, (job.finished_at - job.started_at).total_seconds()),
                1,
            )

        result.append(
            {
                "id": job.id,
                "filename": job.filename,
                "started_at": job.started_at,
                "finished_at": job.finished_at,
                "status": job.status,
                "duration_seconds": duration_seconds,
                "total_consumed_g": round(consumed, 1),
                "slots": {
                    letter: {
                        "spool_id": getattr(job, f"slot_{letter}_spool_id"),
                        "before_g": getattr(job, f"slot_{letter}_before"),
                        "after_g": getattr(job, f"slot_{letter}_after"),
                    }
                    for letter in "abcd"
                },
            }
        )

    return result
