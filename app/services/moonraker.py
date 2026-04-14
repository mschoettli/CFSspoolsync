"""Moonraker integration and print lifecycle tracking."""

import asyncio
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)

MOONRAKER_URL = os.getenv("MOONRAKER_URL", "http://192.168.178.192:7125")
POLL_INTERVAL = int(os.getenv("MOONRAKER_POLL_INTERVAL", "5"))

_printer_state: str = "standby"
_current_job_id: Optional[int] = None
_http_client: Optional[httpx.AsyncClient] = None
_live_tick_lock: Optional[asyncio.Lock] = None
_last_live_tick_ts: float = 0.0
LIVE_TICK_MIN_INTERVAL_S = float(os.getenv("MOONRAKER_LIVE_TICK_MIN_INTERVAL_S", "4"))
_current_job_filament_start_m: Optional[float] = None


async def init_http_client() -> None:
    """Initialize one reusable Moonraker HTTP client."""
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(timeout=5)


async def close_http_client() -> None:
    """Close the reusable Moonraker HTTP client."""
    global _http_client
    if _http_client is not None:
        await _http_client.aclose()
        _http_client = None


def _get_live_tick_lock() -> asyncio.Lock:
    """Return one shared lock for on-demand live consumption ticks."""
    global _live_tick_lock
    if _live_tick_lock is None:
        _live_tick_lock = asyncio.Lock()
    return _live_tick_lock


async def _client() -> httpx.AsyncClient:
    """Return an initialized HTTP client instance."""
    if _http_client is None:
        await init_http_client()
    return _http_client


async def _query_objects(object_names: list[str]) -> dict:
    """Query a set of Moonraker printer objects and return their status payload.

    Args:
    -----
        object_names (list[str]):
            Moonraker object names, for example ``print_stats`` or
            ``temperature_sensor chamber``.

    Returns:
    --------
        dict:
            Status mapping from object name to object payload.
    """
    if not object_names:
        return {}

    query = "&".join(quote(name, safe="_") for name in object_names)
    client = await _client()
    response = await client.get(f"{MOONRAKER_URL}/printer/objects/query?{query}")
    response.raise_for_status()
    return response.json().get("result", {}).get("status", {})


async def _list_objects() -> list[str]:
    """Return all available Moonraker printer object names.

    Returns:
    --------
        list[str]:
            Available object names from ``/printer/objects/list``.
    """
    client = await _client()
    response = await client.get(f"{MOONRAKER_URL}/printer/objects/list")
    response.raise_for_status()
    objects = response.json().get("result", {}).get("objects", [])
    return [obj for obj in objects if isinstance(obj, str)]


def _pick_env_sensor_objects(objects: list[str]) -> list[str]:
    """Select CFS/chamber related sensor objects from Moonraker object list.

    Args:
    -----
        objects (list[str]):
            All printer object names.

    Returns:
    --------
        list[str]:
            Sensor object names ordered by relevance.
    """
    selected: list[str] = []
    for name in objects:
        lower = name.lower()
        has_cfs_context = any(token in lower for token in ("cfs", "chamber", "box", "cabinet"))
        is_env_sensor = any(
            token in lower
            for token in ("temperature_sensor", "humidity_sensor", "htu21d", "bme280", "aht10")
        )
        if has_cfs_context and is_env_sensor:
            selected.append(name)
    return selected


async def get_printer_status() -> dict:
    """Fetch current printer status from Moonraker."""
    try:
        base_objects = ["print_stats", "toolhead", "heater_bed", "extruder", "display_status"]
        status = await _query_objects(base_objects)

        try:
            env_objects = _pick_env_sensor_objects(await _list_objects())
            if env_objects:
                status.update(await _query_objects(env_objects))
        except Exception as exc:
            logger.debug("Moonraker env sensor lookup failed: %s", exc)

        return status
    except Exception as exc:
        logger.debug("Moonraker unreachable: %s", exc)
        return {}


async def _on_print_started() -> None:
    """Create a print job snapshot on printing start transition."""
    global _current_job_id, _current_job_filament_start_m

    from app.database import SessionLocal
    from app.models import PrintJob, Spool
    from app.services.ssh_client import get_all_slots

    db = SessionLocal()
    try:
        slots = await asyncio.to_thread(get_all_slots)
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        filename = ""
        filament_used_m = 0.0
        try:
            client = await _client()
            response = await client.get(
                f"{MOONRAKER_URL}/printer/objects/query?print_stats"
            )
            stats = response.json().get("result", {}).get("status", {}).get("print_stats", {})
            filename = stats.get("filename", "")
            filament_used_raw = float(stats.get("filament_used", 0.0) or 0.0)
            filament_used_m = max(0.0, filament_used_raw / 1000.0)
        except Exception:
            logger.debug("Could not read filename for print start event")

        running_jobs = (
            db.query(PrintJob)
            .filter(PrintJob.status == "running")
            .order_by(PrintJob.started_at.desc(), PrintJob.id.desc())
            .all()
        )
        job: PrintJob | None = None
        if running_jobs:
            same_file = next(
                (
                    job
                    for job in running_jobs
                    if filename
                    and job.filename
                    and job.filename.strip() == filename.strip()
                ),
                None,
            )
            if same_file is not None:
                logger.info(
                    "[Moonraker] Reusing running job #%s for %s (refreshing snapshots)",
                    same_file.id,
                    same_file.filename,
                )
                job = same_file

            if job is None:
                for stale_job in running_jobs:
                    stale_job.status = "cancelled"
                    stale_job.finished_at = stale_job.finished_at or now

        if job is None:
            job = PrintJob(
                started_at=now,
                status="running",
                filename=filename,
            )
            db.add(job)
        elif filename:
            job.filename = filename

        letters = {1: "a", 2: "b", 3: "c", 4: "d"}
        active_spools = {
            spool.cfs_slot: spool
            for spool in db.query(Spool).filter(Spool.status == "aktiv").all()
            if spool.cfs_slot
        }

        for letter in letters.values():
            setattr(job, f"snap_{letter}_before", None)
            setattr(job, f"snap_{letter}_after", None)
            setattr(job, f"slot_{letter}_spool_id", None)
            setattr(job, f"slot_{letter}_before", None)
            setattr(job, f"slot_{letter}_after", None)

        for slot_num, slot_data in slots.items():
            letter = letters[slot_num]
            if not slot_data or not slot_data.get("loaded"):
                continue

            setattr(job, f"snap_{letter}_before", slot_data["remain_len"])
            setattr(job, f"snap_{letter}_after", slot_data["remain_len"])
            spool = active_spools.get(slot_num)
            if spool:
                setattr(job, f"slot_{letter}_spool_id", spool.id)
                setattr(job, f"slot_{letter}_before", spool.remaining_weight)
                setattr(job, f"slot_{letter}_after", spool.remaining_weight)
            else:
                logger.debug(
                    "[Moonraker] Slot %s loaded but no active spool assignment found",
                    letter.upper(),
                )

        db.commit()
        db.refresh(job)

        _current_job_id = job.id
        _current_job_filament_start_m = filament_used_m
        logger.info("[Moonraker] Print job #%s started - %s", job.id, filename)
    except Exception as exc:
        logger.error("on_print_started error: %s", exc)
        db.rollback()
    finally:
        db.close()


async def _on_print_ended(final_state: str) -> None:
    """Finalize the current print job and apply measured filament consumption."""
    global _current_job_id, _current_job_filament_start_m

    from app.database import SessionLocal
    from app.models import PrintJob, Spool
    from app.services.ssh_client import get_all_slots, meters_to_grams

    db = SessionLocal()
    try:
        if _current_job_id is None:
            fallback_job = (
                db.query(PrintJob)
                .filter(PrintJob.status == "running")
                .order_by(PrintJob.started_at.desc(), PrintJob.id.desc())
                .first()
            )
            if not fallback_job:
                logger.warning("[Moonraker] Print ended but no active job was tracked")
                return
            _current_job_id = fallback_job.id

        job = db.query(PrintJob).filter(PrintJob.id == _current_job_id).first()
        if not job:
            fallback_job = (
                db.query(PrintJob)
                .filter(PrintJob.status == "running")
                .order_by(PrintJob.started_at.desc(), PrintJob.id.desc())
                .first()
            )
            if not fallback_job:
                logger.error("Job #%s not found", _current_job_id)
                return
            job = fallback_job
            _current_job_id = job.id

        slots = await asyncio.to_thread(get_all_slots)
        current_filament_m = await _get_current_filament_used_m()
        active_slot_num = await _get_active_cfs_slot()
        _apply_consumption_delta(
            job,
            slots,
            db,
            meters_to_grams,
            final_log=True,
            current_filament_used_m=current_filament_m,
            active_slot_num=active_slot_num,
        )

        job.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
        job.status = "finished" if final_state == "complete" else final_state

        db.commit()
        logger.info("[Moonraker] Job #%s completed (%s)", job.id, job.status)
        _current_job_id = None
        _current_job_filament_start_m = None
    except Exception as exc:
        logger.error("on_print_ended error: %s", exc)
        db.rollback()
    finally:
        db.close()


async def polling_loop() -> None:
    """Poll Moonraker and emit transition events for print lifecycle changes."""
    global _printer_state

    logger.info("[Moonraker] Polling started (interval: %ss)", POLL_INTERVAL)
    while True:
        try:
            await asyncio.sleep(POLL_INTERVAL)

            status = await get_printer_status()
            if not status:
                continue

            current = status.get("print_stats", {}).get("state", "standby")

            if _printer_state != "printing" and current == "printing":
                await _on_print_started()
            elif _printer_state == "printing" and current == "printing":
                await _update_running_job_progress()
            elif _printer_state == "printing" and current in (
                "complete",
                "standby",
                "error",
                "cancelled",
            ):
                await _on_print_ended(current)

            _printer_state = current

        except asyncio.CancelledError:
            logger.info("[Moonraker] Polling stopped")
            break
        except Exception as exc:
            logger.error("[Moonraker] Polling error: %s", exc)


async def _get_current_filament_used_m() -> Optional[float]:
    """Read current print_stats.filament_used and convert mm->m."""
    try:
        status = await _query_objects(["print_stats"])
        print_stats = status.get("print_stats", {}) if isinstance(status, dict) else {}
        filament_used_raw = float(print_stats.get("filament_used", 0.0) or 0.0)
        return max(0.0, filament_used_raw / 1000.0)
    except Exception as exc:
        logger.debug("Could not read print_stats.filament_used: %s", exc)
        return None


def _parse_active_slot_value(value: Any) -> Optional[int]:
    """Parse active slot values from Moonraker payloads."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        slot = int(value)
        return slot if slot in (1, 2, 3, 4) else None

    text = str(value).strip().upper()
    if text in {"A", "B", "C", "D"}:
        return {"A": 1, "B": 2, "C": 3, "D": 4}[text]
    try:
        slot = int(text)
        return slot if slot in (1, 2, 3, 4) else None
    except ValueError:
        return None


def _extract_active_cfs_slot(status: dict[str, Any]) -> Optional[int]:
    """Extract active CFS slot from known Moonraker object fields."""
    key_candidates = (
        "active_cfs_slot",
        "cfs_active_slot",
        "active_slot",
        "current_slot",
        "slot",
    )
    object_candidates = ("print_stats", "display_status", "toolhead")

    for object_name in object_candidates:
        payload = status.get(object_name, {})
        if not isinstance(payload, dict):
            continue
        for key in key_candidates:
            parsed = _parse_active_slot_value(payload.get(key))
            if parsed is not None:
                return parsed
        info = payload.get("info")
        if isinstance(info, dict):
            for key in key_candidates:
                parsed = _parse_active_slot_value(info.get(key))
                if parsed is not None:
                    return parsed
    return None


async def _get_active_cfs_slot() -> Optional[int]:
    """Read active CFS slot from Moonraker status if available."""
    try:
        status = await _query_objects(["print_stats", "display_status", "toolhead"])
        return _extract_active_cfs_slot(status if isinstance(status, dict) else {})
    except Exception as exc:
        logger.debug("Could not read active CFS slot: %s", exc)
        return None


def _apply_consumption_delta(
    job,
    slots,
    db,
    meters_to_grams,
    final_log: bool,
    current_filament_used_m: Optional[float] = None,
    active_slot_num: Optional[int] = None,
) -> None:
    """Update spool/job after-weights, preferring filament_used over remainLen."""
    from app.models import Spool
    global _current_job_filament_start_m

    letters = {1: "a", 2: "b", 3: "c", 4: "d"}
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    slot_entries: dict[str, dict[str, Any]] = {}
    remainlen_weights: dict[str, float] = {}
    any_positive_remainlen_delta = False

    for slot_num, slot_data in slots.items():
        letter = letters[slot_num]
        if not slot_data:
            logger.debug("[Moonraker] Skip slot %s: no live slot data", letter.upper())
            continue

        current_len = slot_data.get("remain_len")
        if current_len is None:
            logger.debug("[Moonraker] Skip slot %s: remain_len missing", letter.upper())
            continue
        setattr(job, f"snap_{letter}_after", current_len)

        spool_id = getattr(job, f"slot_{letter}_spool_id")
        before_len = getattr(job, f"snap_{letter}_before")
        before_weight = getattr(job, f"slot_{letter}_before")
        if not spool_id or before_len is None or before_weight is None:
            logger.debug(
                "[Moonraker] Skip slot %s: missing snapshot fields (spool_id=%s, before_len=%s, before_weight=%s)",
                letter.upper(),
                spool_id,
                before_len,
                before_weight,
            )
            continue

        spool = db.query(Spool).filter(Spool.id == spool_id).first()
        if not spool:
            logger.debug(
                "[Moonraker] Skip slot %s: spool #%s not found",
                letter.upper(),
                spool_id,
            )
            continue

        slot_entries[letter] = {
            "slot_num": slot_num,
            "spool": spool,
            "before_weight": float(before_weight),
        }

        consumed_m = max(0.0, before_len - current_len)
        if consumed_m > 0.001:
            any_positive_remainlen_delta = True
        consumed_g = round(
            meters_to_grams(consumed_m, spool.diameter, spool.density),
            1,
        )
        remainlen_weights[letter] = round(
            max(0.0, min(spool.initial_weight, before_weight - consumed_g)),
            1,
        )

        if final_log:
            logger.info(
                "[Moonraker] remainLen slot %s consumed=%.1fg projected=%.1fg",
                letter.upper(),
                consumed_g,
                remainlen_weights[letter],
            )

    # Primary path: filament_used deltas, mapped to one reliable active slot.
    used_source = "fallback_none"
    applied = False
    target_letter: Optional[str] = None
    if active_slot_num in letters:
        candidate = letters[active_slot_num]
        if candidate in slot_entries:
            target_letter = candidate
            used_source = "filament_used"
        else:
            logger.debug(
                "[Moonraker] Active slot %s has no tracked spool mapping",
                active_slot_num,
            )
    elif len(slot_entries) == 1:
        target_letter = next(iter(slot_entries))
        used_source = "filament_used_single_slot"
    else:
        logger.debug(
            "[Moonraker] No reliable active slot for filament_used (active_slot=%s, tracked_slots=%s)",
            active_slot_num,
            sorted(slot_entries.keys()),
        )

    if (
        target_letter
        and current_filament_used_m is not None
        and _current_job_filament_start_m is not None
    ):
        consumed_m_total = max(0.0, current_filament_used_m - _current_job_filament_start_m)
        if consumed_m_total > 0.001:
            entry = slot_entries[target_letter]
            spool = entry["spool"]
            before_weight = entry["before_weight"]
            consumed_g = round(
                meters_to_grams(consumed_m_total, spool.diameter, spool.density),
                1,
            )
            new_weight = round(
                max(0.0, min(spool.initial_weight, before_weight - consumed_g)),
                1,
            )
            previous_weight = spool.remaining_weight
            spool.remaining_weight = new_weight
            spool.updated_at = now
            setattr(job, f"slot_{target_letter}_after", new_weight)
            applied = True
            if final_log:
                logger.info(
                    "[Moonraker] %s slot %s: -%.1fg -> %.1fg left (prev %.1fg)",
                    used_source,
                    target_letter.upper(),
                    consumed_g,
                    new_weight,
                    previous_weight,
                )
            else:
                logger.debug(
                    "[Moonraker] %s slot %s: -%.1fg -> %.1fg left",
                    used_source,
                    target_letter.upper(),
                    consumed_g,
                    new_weight,
                )

    # Secondary path: only use remainLen when filament_used path was not applied.
    if not applied and any_positive_remainlen_delta:
        for letter, entry in slot_entries.items():
            if letter not in remainlen_weights:
                continue
            spool = entry["spool"]
            new_weight = remainlen_weights[letter]
            previous_weight = spool.remaining_weight
            spool.remaining_weight = new_weight
            spool.updated_at = now
            setattr(job, f"slot_{letter}_after", new_weight)
            if final_log:
                logger.info(
                    "[Moonraker] remain_len slot %s: -> %.1fg left (prev %.1fg)",
                    letter.upper(),
                    new_weight,
                    previous_weight,
                )
        used_source = "remain_len"

    logger.debug(
        "[Moonraker] Consumption update source=%s active_slot=%s filament_used_m=%s",
        used_source,
        active_slot_num,
        current_filament_used_m,
    )


async def _update_running_job_progress() -> None:
    """Apply in-print remainLen deltas so UI reflects live spool consumption."""
    global _current_job_id

    if _current_job_id is None:
        return

    from app.database import SessionLocal
    from app.models import PrintJob
    from app.services.ssh_client import get_all_slots, meters_to_grams

    db = SessionLocal()
    try:
        job = db.query(PrintJob).filter(PrintJob.id == _current_job_id).first()
        if not job or job.status != "running":
            return

        slots = await asyncio.to_thread(get_all_slots)
        current_filament_m = await _get_current_filament_used_m()
        active_slot_num = await _get_active_cfs_slot()
        _apply_consumption_delta(
            job,
            slots,
            db,
            meters_to_grams,
            final_log=False,
            current_filament_used_m=current_filament_m,
            active_slot_num=active_slot_num,
        )
        db.commit()
    except Exception as exc:
        logger.error("update_running_job_progress error: %s", exc)
        db.rollback()
    finally:
        db.close()


async def ensure_live_consumption_tick(current_state: str) -> None:
    """Apply one throttled live consumption update when printer is printing.

    This endpoint-triggered safety net keeps CFS weights moving even when the
    background polling loop is not running as expected.
    """
    global _last_live_tick_ts

    if current_state != "printing":
        return

    lock = _get_live_tick_lock()
    async with lock:
        now = time.monotonic()
        if now - _last_live_tick_ts < LIVE_TICK_MIN_INTERVAL_S:
            return
        _last_live_tick_ts = now

        if _current_job_id is None:
            await _on_print_started()
        await _update_running_job_progress()
