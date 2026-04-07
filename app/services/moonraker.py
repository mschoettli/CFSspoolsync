"""Moonraker integration and print lifecycle tracking."""

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

MOONRAKER_URL = os.getenv("MOONRAKER_URL", "http://192.168.178.192:7125")
POLL_INTERVAL = int(os.getenv("MOONRAKER_POLL_INTERVAL", "10"))

_printer_state: str = "standby"
_current_job_id: Optional[int] = None
_http_client: Optional[httpx.AsyncClient] = None


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


async def _client() -> httpx.AsyncClient:
    """Return an initialized HTTP client instance."""
    if _http_client is None:
        await init_http_client()
    return _http_client


async def get_printer_status() -> dict:
    """Fetch current printer status from Moonraker."""
    try:
        params = "print_stats&toolhead&heater_bed&extruder&display_status"
        client = await _client()
        response = await client.get(
            f"{MOONRAKER_URL}/printer/objects/query?{params}"
        )
        response.raise_for_status()
        return response.json().get("result", {}).get("status", {})
    except Exception as exc:
        logger.debug("Moonraker unreachable: %s", exc)
        return {}


async def _on_print_started() -> None:
    """Create a print job snapshot on printing start transition."""
    global _current_job_id

    from app.database import SessionLocal
    from app.models import PrintJob, Spool
    from app.services.ssh_client import get_all_slots

    db = SessionLocal()
    try:
        slots = await asyncio.to_thread(get_all_slots)

        filename = ""
        try:
            client = await _client()
            response = await client.get(
                f"{MOONRAKER_URL}/printer/objects/query?print_stats"
            )
            stats = response.json().get("result", {}).get("status", {}).get("print_stats", {})
            filename = stats.get("filename", "")
        except Exception:
            logger.debug("Could not read filename for print start event")

        job = PrintJob(
            started_at=datetime.now(timezone.utc).replace(tzinfo=None),
            status="running",
            filename=filename,
        )

        letters = {1: "a", 2: "b", 3: "c", 4: "d"}
        active_spools = {
            spool.cfs_slot: spool
            for spool in db.query(Spool).filter(Spool.status == "aktiv").all()
            if spool.cfs_slot
        }

        for slot_num, slot_data in slots.items():
            letter = letters[slot_num]
            if not slot_data or not slot_data.get("loaded"):
                continue

            setattr(job, f"snap_{letter}_before", slot_data["remain_len"])
            spool = active_spools.get(slot_num)
            if spool:
                setattr(job, f"slot_{letter}_spool_id", spool.id)
                setattr(job, f"slot_{letter}_before", spool.remaining_weight)

        db.add(job)
        db.commit()
        db.refresh(job)

        _current_job_id = job.id
        logger.info("[Moonraker] Print job #%s started - %s", job.id, filename)
    except Exception as exc:
        logger.error("on_print_started error: %s", exc)
        db.rollback()
    finally:
        db.close()


async def _on_print_ended(final_state: str) -> None:
    """Finalize the current print job and apply measured filament consumption."""
    global _current_job_id

    if _current_job_id is None:
        logger.warning("[Moonraker] Print ended but no active job was tracked")
        return

    from app.database import SessionLocal
    from app.models import PrintJob, Spool
    from app.services.ssh_client import get_all_slots, meters_to_grams

    db = SessionLocal()
    try:
        job = db.query(PrintJob).filter(PrintJob.id == _current_job_id).first()
        if not job:
            logger.error("Job #%s not found", _current_job_id)
            return

        slots = await asyncio.to_thread(get_all_slots)

        job.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
        job.status = "finished" if final_state == "complete" else final_state

        letters = {1: "a", 2: "b", 3: "c", 4: "d"}
        for slot_num, slot_data in slots.items():
            letter = letters[slot_num]
            if not slot_data:
                continue

            after_len = slot_data["remain_len"]
            setattr(job, f"snap_{letter}_after", after_len)

            spool_id = getattr(job, f"slot_{letter}_spool_id")
            before_len = getattr(job, f"snap_{letter}_before")
            if not spool_id or before_len is None:
                continue

            consumed_m = before_len - after_len
            if consumed_m <= 0:
                continue

            spool = db.query(Spool).filter(Spool.id == spool_id).first()
            if not spool:
                continue

            consumed_g = meters_to_grams(consumed_m, spool.diameter, spool.density)
            new_weight = max(0.0, spool.remaining_weight - consumed_g)
            setattr(job, f"slot_{letter}_after", new_weight)
            spool.remaining_weight = round(new_weight, 1)
            spool.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

            logger.info(
                "[Moonraker] Slot %s: -%.1fg -> %.1fg left",
                letter.upper(),
                consumed_g,
                new_weight,
            )

        db.commit()
        logger.info("[Moonraker] Job #%s completed (%s)", job.id, job.status)
        _current_job_id = None
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
