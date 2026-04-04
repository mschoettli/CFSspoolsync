import os
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

MOONRAKER_URL = os.getenv("MOONRAKER_URL", "http://192.168.178.192:7125")
POLL_INTERVAL = 10  # seconds

# Module-level state (single worker task)
_printer_state: str = "standby"
_current_job_id: Optional[int] = None


# ─── Moonraker helpers ────────────────────────────────────────────────────────

async def get_printer_status() -> dict:
    try:
        params = "print_stats&toolhead&heater_bed&extruder&display_status"
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(
                f"{MOONRAKER_URL}/printer/objects/query?{params}"
            )
            r.raise_for_status()
            return r.json().get("result", {}).get("status", {})
    except Exception as exc:
        logger.debug(f"Moonraker unreachable: {exc}")
        return {}


# ─── Event handlers ───────────────────────────────────────────────────────────

async def _on_print_started():
    global _current_job_id

    from app.database import SessionLocal
    from app.models import PrintJob, Spool
    from app.services.ssh_client import get_all_slots

    db = SessionLocal()
    try:
        # Snapshot CFS state
        slots = get_all_slots()

        # Get filename from Moonraker
        filename = ""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(
                    f"{MOONRAKER_URL}/printer/objects/query?print_stats"
                )
                stats = r.json().get("result", {}).get("status", {}).get("print_stats", {})
                filename = stats.get("filename", "")
        except Exception:
            pass

        job = PrintJob(
            started_at=datetime.now(timezone.utc).replace(tzinfo=None),
            status="running",
            filename=filename,
        )

        letters = {1: "a", 2: "b", 3: "c", 4: "d"}
        for slot_num, slot_data in slots.items():
            letter = letters[slot_num]
            if slot_data and slot_data.get("loaded"):
                setattr(job, f"snap_{letter}_before", slot_data["remain_len"])

                spool = (
                    db.query(Spool)
                    .filter(Spool.cfs_slot == slot_num, Spool.status == "aktiv")
                    .first()
                )
                if spool:
                    setattr(job, f"slot_{letter}_spool_id", spool.id)
                    setattr(job, f"slot_{letter}_before", spool.remaining_weight)

        db.add(job)
        db.commit()
        db.refresh(job)
        _current_job_id = job.id
        logger.info(f"[Moonraker] Druckauftrag #{job.id} gestartet – {filename}")

    except Exception as exc:
        logger.error(f"on_print_started error: {exc}")
        db.rollback()
    finally:
        db.close()


async def _on_print_ended(final_state: str):
    global _current_job_id

    if _current_job_id is None:
        logger.warning("[Moonraker] Druck beendet aber kein aktiver Job gefunden")
        return

    from app.database import SessionLocal
    from app.models import PrintJob, Spool
    from app.services.ssh_client import get_all_slots, meters_to_grams

    db = SessionLocal()
    try:
        job = db.query(PrintJob).filter(PrintJob.id == _current_job_id).first()
        if not job:
            logger.error(f"Job #{_current_job_id} nicht gefunden")
            return

        slots = get_all_slots()

        job.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
        job.status = "finished" if final_state == "complete" else final_state

        letters = {1: "a", 2: "b", 3: "c", 4: "d"}
        for slot_num, slot_data in slots.items():
            letter = letters[slot_num]
            if slot_data:
                after_len = slot_data["remain_len"]
                setattr(job, f"snap_{letter}_after", after_len)

                spool_id = getattr(job, f"slot_{letter}_spool_id")
                before_len = getattr(job, f"snap_{letter}_before")

                if spool_id and before_len is not None:
                    consumed_m = before_len - after_len
                    if consumed_m > 0:
                        spool = db.query(Spool).filter(Spool.id == spool_id).first()
                        if spool:
                            consumed_g = meters_to_grams(
                                consumed_m, spool.diameter, spool.density
                            )
                            new_weight = max(0.0, spool.remaining_weight - consumed_g)
                            setattr(job, f"slot_{letter}_after", new_weight)
                            spool.remaining_weight = round(new_weight, 1)
                            spool.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
                            logger.info(
                                f"[Moonraker] Slot {letter.upper()}: "
                                f"−{consumed_g:.1f}g → verbleibend {new_weight:.1f}g"
                            )

        db.commit()
        logger.info(f"[Moonraker] Job #{job.id} abgeschlossen ({job.status})")
        _current_job_id = None

    except Exception as exc:
        logger.error(f"on_print_ended error: {exc}")
        db.rollback()
    finally:
        db.close()


# ─── Main polling loop ────────────────────────────────────────────────────────

async def polling_loop(_app):
    global _printer_state

    logger.info("[Moonraker] Polling gestartet (Intervall: 10 s)")

    while True:
        try:
            await asyncio.sleep(POLL_INTERVAL)

            status = await get_printer_status()
            if not status:
                continue

            current = (
                status.get("print_stats", {}).get("state", "standby")
            )

            # Transition: idle → printing
            if _printer_state != "printing" and current == "printing":
                await _on_print_started()

            # Transition: printing → done/cancelled/error
            elif _printer_state == "printing" and current in (
                "complete", "standby", "error", "cancelled"
            ):
                await _on_print_ended(current)

            _printer_state = current

        except asyncio.CancelledError:
            logger.info("[Moonraker] Polling gestoppt")
            break
        except Exception as exc:
            logger.error(f"[Moonraker] Polling-Fehler: {exc}")
