from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import PrintJob

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("")
def list_jobs(limit: int = Query(30, ge=1, le=200), offset: int = Query(0, ge=0), db: Session = Depends(get_db)) -> list[dict]:
    jobs = (
        db.query(PrintJob)
        .order_by(PrintJob.started_at.desc(), PrintJob.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    result: list[dict] = []
    for job in jobs:
        duration_seconds = None
        if job.started_at and job.finished_at:
            duration_seconds = max(0.0, (job.finished_at - job.started_at).total_seconds())
        result.append(
            {
                "id": job.id,
                "filename": job.filename,
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "finished_at": job.finished_at.isoformat() if job.finished_at else None,
                "status": job.status,
                "duration_seconds": round(duration_seconds, 1) if duration_seconds is not None else None,
                "live_consumed_mm": round(float(job.live_consumed_mm or 0.0), 1),
                "total_consumed_g": round(float(job.live_consumed_g or 0.0), 1),
                "live_consumed_quality": job.live_consumed_quality,
                "consumption_source": job.consumption_source,
                "data_quality_flags": [],
                "slots": {
                    "a": {"spool_id": job.slot_a_spool_id, "before_g": job.slot_a_before, "after_g": job.slot_a_after},
                    "b": {"spool_id": job.slot_b_spool_id, "before_g": job.slot_b_before, "after_g": job.slot_b_after},
                    "c": {"spool_id": job.slot_c_spool_id, "before_g": job.slot_c_before, "after_g": job.slot_c_after},
                    "d": {"spool_id": job.slot_d_spool_id, "before_g": job.slot_d_before, "after_g": job.slot_d_after},
                },
            }
        )

    return result


@router.post("/admin/delete-history")
def delete_job_history(confirm: str = Query("", description="Must be DELETE"), db: Session = Depends(get_db)) -> dict:
    if confirm.strip().upper() != "DELETE":
        return {"ok": False, "deleted": 0, "detail": "Set confirm=DELETE"}
    deleted = db.query(PrintJob).delete(synchronize_session=False)
    db.commit()
    return {"ok": True, "deleted": int(deleted)}
