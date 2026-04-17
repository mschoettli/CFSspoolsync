import asyncio
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.models import PrintJob, Spool
from app.services.cfs_agent_client import fetch_cfs_agent_state
from app.services.conversion import grams_from_mm
from app.services.moonraker_client import fetch_moonraker_status


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class TelemetryHub:
    def __init__(self) -> None:
        self._condition = asyncio.Condition()
        self._version = 0
        self._snapshot: dict[str, Any] = {
            "reachable": False,
            "state": "booting",
            "filename": "",
            "progress": 0.0,
            "print_duration_seconds": 0.0,
            "filament_used_raw": 0.0,
            "live_consumed_mm": 0.0,
            "live_consumed_g": 0.0,
            "live_consumed_quality": "estimated",
            "consumption_source": "boot",
            "degraded": True,
            "cfs": {
                "reachable": False,
                "active_slot": None,
                "slots": {},
                "degraded_reason": "boot",
            },
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    async def update(self, payload: dict[str, Any]) -> None:
        async with self._condition:
            self._version += 1
            merged = {**self._snapshot, **payload}
            merged["updated_at"] = datetime.now(timezone.utc).isoformat()
            merged["degraded"] = not bool(merged.get("reachable", False))
            self._snapshot = merged
            self._condition.notify_all()

    def snapshot(self) -> tuple[int, dict[str, Any]]:
        return self._version, dict(self._snapshot)

    async def wait_for_update(self, last_seen_version: int, timeout_seconds: float = 10.0) -> tuple[int, dict[str, Any]]:
        async with self._condition:
            if self._version == last_seen_version:
                try:
                    await asyncio.wait_for(self._condition.wait(), timeout=timeout_seconds)
                except asyncio.TimeoutError:
                    pass
            return self._version, dict(self._snapshot)


def _slot_letter(slot: Optional[int]) -> Optional[str]:
    mapping = {1: "a", 2: "b", 3: "c", 4: "d"}
    return mapping.get(slot)


def _get_running_job(db: Session) -> Optional[PrintJob]:
    return (
        db.query(PrintJob)
        .filter(PrintJob.status == "running")
        .order_by(PrintJob.started_at.desc(), PrintJob.id.desc())
        .first()
    )


def _init_running_job(db: Session, filename: str, filament_raw: float) -> PrintJob:
    job = PrintJob(
        filename=filename,
        started_at=_utcnow_naive(),
        status="running",
        filament_used_start_raw=filament_raw,
        filament_used_last_raw=filament_raw,
        live_consumed_mm=0.0,
        live_consumed_g=0.0,
        live_consumed_quality="estimated",
        consumption_source="filament_used_global_estimated",
    )

    active_spools = {
        spool.cfs_slot: spool
        for spool in db.query(Spool).filter(Spool.status == "aktiv").all()
        if spool.cfs_slot in (1, 2, 3, 4)
    }

    for slot in (1, 2, 3, 4):
        letter = _slot_letter(slot)
        spool = active_spools.get(slot)
        if not letter:
            continue
        if spool:
            setattr(job, f"slot_{letter}_spool_id", spool.id)
            setattr(job, f"slot_{letter}_before", float(spool.remaining_weight or 0.0))
            setattr(job, f"slot_{letter}_after", float(spool.remaining_weight or 0.0))

    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def _finalize_running_job(db: Session, job: Optional[PrintJob], state: str) -> None:
    if not job:
        return
    if state == "printing":
        return
    job.status = "finished" if state in {"complete", "standby"} else state
    job.finished_at = _utcnow_naive()
    db.commit()


def _apply_live_delta(db: Session, job: PrintJob, filament_used_raw: float, active_slot: Optional[int]) -> None:
    previous = float(job.filament_used_last_raw or filament_used_raw)
    raw_delta = filament_used_raw - previous
    source = "filament_used_global_estimated"

    if raw_delta < 0:
        raw_delta = 0.0
        source = "filament_reset_ignored"
    if raw_delta > settings.max_filament_raw_delta_mm:
        raw_delta = 0.0
        source = "filament_outlier_ignored"

    measured = False
    consumed_g = 0.0

    if raw_delta > 0:
        letter = _slot_letter(active_slot)
        spool = None
        if letter:
            spool_id = getattr(job, f"slot_{letter}_spool_id")
            if spool_id:
                spool = db.query(Spool).filter(Spool.id == spool_id).first()

        if spool:
            consumed_g = grams_from_mm(raw_delta, float(spool.diameter or 0.0), float(spool.density or 0.0))
            measured = consumed_g > 0
            if measured:
                spool.remaining_weight = round(max(0.0, float(spool.remaining_weight or 0.0) - consumed_g), 1)
                setattr(job, f"slot_{letter}_after", float(spool.remaining_weight))
                source = "filament_used_global_slot"

        if not measured:
            consumed_g = grams_from_mm(raw_delta, settings.default_filament_diameter_mm, settings.default_filament_density)
            source = "filament_used_global_estimated"

        job.live_consumed_mm = round(float(job.live_consumed_mm or 0.0) + raw_delta, 1)
        job.live_consumed_g = round(float(job.live_consumed_g or 0.0) + max(0.0, consumed_g), 1)

    job.live_consumed_quality = "measured" if measured else "estimated"
    job.consumption_source = source
    job.filament_used_last_raw = filament_used_raw
    db.commit()


async def telemetry_polling_loop(hub: TelemetryHub, poll_seconds: float) -> None:
    offline_streak = 0
    while True:
        moon = await fetch_moonraker_status()
        cfs = await fetch_cfs_agent_state()
        reachable = bool(moon.get("reachable", False))
        state = str(moon.get("state", "unknown"))

        if reachable:
            offline_streak = 0
        else:
            offline_streak += 1

        db = SessionLocal()
        try:
            job = _get_running_job(db)

            if state == "printing":
                if not job:
                    job = _init_running_job(
                        db,
                        filename=str(moon.get("filename", "")),
                        filament_raw=float(moon.get("filament_used_raw", 0.0) or 0.0),
                    )
                _apply_live_delta(
                    db,
                    job,
                    filament_used_raw=float(moon.get("filament_used_raw", 0.0) or 0.0),
                    active_slot=cfs.get("active_slot"),
                )
            elif not reachable and job and offline_streak < max(1, settings.telemetry_offline_grace_cycles):
                pass
            else:
                _finalize_running_job(db, job, state)
                job = _get_running_job(db)

            live_mm = float(job.live_consumed_mm) if job else 0.0
            live_g = float(job.live_consumed_g) if job else 0.0
            quality = str(job.live_consumed_quality) if job and job.live_consumed_quality else "estimated"
            source = str(job.consumption_source) if job and job.consumption_source else "none"

            snapshot = {
                **moon,
                "live_consumed_mm": round(live_mm, 1),
                "live_consumed_g": round(live_g, 1),
                "live_consumed_quality": quality,
                "consumption_source": source,
                "cfs": cfs,
            }
            await hub.update(snapshot)
        finally:
            db.close()

        await asyncio.sleep(max(0.5, poll_seconds))
