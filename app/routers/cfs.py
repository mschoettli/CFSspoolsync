"""HTTP routes for CFS slot data and slot assignment."""

import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Spool
from app.schemas.spool import SpoolOut
from app.services import ssh_client
from app.services.spool_defaults import get_default_tare_weight_g

router = APIRouter(prefix="/api/cfs", tags=["cfs"])


@router.get("")
def get_cfs_state(db: Session = Depends(get_db)):
    """Return the current CFS slot state from active DB assignments."""
    active = db.query(Spool).filter(Spool.status == "aktiv").all()
    slot_map = {
        spool.cfs_slot: SpoolOut.model_validate(spool).model_dump()
        for spool in active
        if spool.cfs_slot
    }
    return {
        "slots": [
            {
                "slot": i,
                "key": f"Slot {i}",
                "spool": slot_map.get(i),
            }
            for i in range(1, 5)
        ]
    }


@router.get("/live")
async def get_cfs_live():
    """Read live CFS slot data from the printer via SSH."""
    slots = await asyncio.to_thread(ssh_client.get_all_slots)
    reachable = any(value is not None for value in slots.values())
    return {"reachable": reachable, "slots": slots}


@router.post("/sync")
async def sync_from_k2(db: Session = Depends(get_db)):
    """Sync active spool weights from live K2 remain-length values."""
    slots = await asyncio.to_thread(ssh_client.get_all_slots)
    if all(value is None for value in slots.values()):
        raise HTTPException(503, "K2 nicht erreichbar")

    active_spools = {
        spool.cfs_slot: spool
        for spool in db.query(Spool).filter(Spool.status == "aktiv").all()
        if spool.cfs_slot
    }

    updated = []
    removed = []
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    for slot_num, slot_data in slots.items():
        if slot_data is None:
            continue

        spool = active_spools.get(slot_num)
        if not slot_data.get("loaded"):
            if spool:
                spool.cfs_slot = None
                spool.status = "lager"
                spool.updated_at = now
                removed.append(
                    {
                        "slot": slot_num,
                        "spool_id": spool.id,
                        "old_status": "aktiv",
                        "new_status": "lager",
                    }
                )
            continue

        if not spool:
            continue

        if spool.tare_weight_g is None:
            default_tare = get_default_tare_weight_g(spool.brand, spool.material, db)
            if default_tare is not None:
                spool.tare_weight_g = default_tare

        new_weight = round(
            ssh_client.meters_to_grams(
                slot_data["remain_len"], spool.diameter, spool.density
            ),
            1,
        )
        raw_k2_g = new_weight
        applied_factor = spool.calibration_factor if spool.calibration_factor else None
        if applied_factor is not None:
            new_weight = round(raw_k2_g * applied_factor, 1)
        new_weight = max(0.0, min(new_weight, spool.initial_weight))
        old_weight = spool.remaining_weight
        spool.remaining_weight = new_weight
        spool.updated_at = now
        updated.append(
            {
                "slot": slot_num,
                "key": slot_data["key"],
                "spool_id": spool.id,
                "old_g": old_weight,
                "new_g": new_weight,
                "raw_k2_g": raw_k2_g,
                "applied_factor": applied_factor,
                "source": "k2_calibrated" if applied_factor is not None else "k2_raw",
            }
        )

    db.commit()
    return {
        "synced": len(updated),
        "updates": updated,
        "removed_count": len(removed),
        "removed": removed,
    }


@router.get("/slot/{slot_num}/read")
async def read_slot_live(slot_num: int):
    """Read one CFS slot directly from the printer via SSH."""
    if slot_num not in (1, 2, 3, 4):
        raise HTTPException(400, "Slot muss 1-4 sein")

    data = await asyncio.to_thread(ssh_client.get_slot, slot_num)
    if data is None:
        raise HTTPException(503, "K2 nicht erreichbar oder Slot leer")
    return data


@router.post("/slot/{slot_num}/assign/{spool_id}")
def assign_spool(slot_num: int, spool_id: int, db: Session = Depends(get_db)):
    """Assign a storage spool to one CFS slot."""
    if slot_num not in (1, 2, 3, 4):
        raise HTTPException(400, "Slot muss 1-4 sein")

    occupied = (
        db.query(Spool)
        .filter(Spool.cfs_slot == slot_num, Spool.status == "aktiv")
        .first()
    )
    if occupied:
        raise HTTPException(400, f"Slot {slot_num} ist bereits belegt (Spule #{occupied.id})")

    spool = db.query(Spool).filter(Spool.id == spool_id).first()
    if not spool:
        raise HTTPException(404, "Spule nicht gefunden")
    if spool.status != "lager":
        raise HTTPException(400, "Spule ist nicht im Lager")

    spool.cfs_slot = slot_num
    spool.status = "aktiv"
    spool.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    return {"ok": True, "spool_id": spool_id, "slot": slot_num}


@router.post("/slot/{slot_num}/remove")
def remove_spool(slot_num: int, db: Session = Depends(get_db)):
    """Move an active spool from slot back to storage."""
    spool = (
        db.query(Spool)
        .filter(Spool.cfs_slot == slot_num, Spool.status == "aktiv")
        .first()
    )
    if not spool:
        raise HTTPException(404, f"Kein aktiver Slot {slot_num}")

    spool.cfs_slot = None
    spool.status = "lager"
    spool.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    return {"ok": True, "spool_id": spool.id}
