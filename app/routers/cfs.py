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
SYNC_CHANGE_THRESHOLD_G = 0.1


def _is_replacement_detected(slot_data: dict, spool: Spool) -> bool:
    """Return True when live slot data clearly indicates a different spool."""
    live_serial = str(slot_data.get("serial_num") or "").strip()
    known_serial = str(spool.serial_num or "").strip()
    if live_serial and known_serial and live_serial != known_serial:
        return True
    return False


def _create_spool_from_slot(slot_num: int, slot_data: dict, db: Session, now: datetime) -> Spool:
    """Create one active spool entry from live CFS slot metadata."""
    material = str(slot_data.get("material") or "").strip() or "Unbekannt"
    brand = str(slot_data.get("brand") or "").strip()
    name = str(slot_data.get("name") or "").strip()
    color = str(slot_data.get("color") or "").strip() or "#888888"
    nozzle_min = int(slot_data.get("nozzle_min") or 190)
    nozzle_max = int(slot_data.get("nozzle_max") or 230)
    diameter = float(slot_data.get("diameter") or 1.75)
    density = float(slot_data.get("density") or 1.24)
    serial_num = str(slot_data.get("serial_num") or "").strip()

    remaining_weight = round(max(0.0, float(slot_data.get("remaining_grams") or 0.0)), 1)
    initial_weight = round(max(remaining_weight, 1.0), 1)

    tare_weight = get_default_tare_weight_g(brand, material, db)
    spool = Spool(
        material=material,
        color=color,
        brand=brand,
        name=name,
        nozzle_min=nozzle_min,
        nozzle_max=nozzle_max,
        bed_temp=60,
        initial_weight=initial_weight,
        remaining_weight=remaining_weight,
        status="aktiv",
        cfs_slot=slot_num,
        serial_num=serial_num,
        diameter=diameter,
        density=density,
        tare_weight_g=tare_weight,
        updated_at=now,
    )
    db.add(spool)
    db.flush()
    return spool


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
    created = []
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
            created_spool = _create_spool_from_slot(slot_num, slot_data, db, now)
            active_spools[slot_num] = created_spool
            created.append(
                {
                    "slot": slot_num,
                    "spool_id": created_spool.id,
                    "source": "auto_created_from_cfs",
                }
            )
            continue

        if _is_replacement_detected(slot_data, spool):
            previous_spool_id = spool.id
            spool.cfs_slot = None
            spool.status = "lager"
            spool.updated_at = now
            removed.append(
                {
                    "slot": slot_num,
                    "spool_id": previous_spool_id,
                    "old_status": "aktiv",
                    "new_status": "lager",
                    "reason": "replaced_by_new_cfs_spool",
                }
            )

            created_spool = _create_spool_from_slot(slot_num, slot_data, db, now)
            active_spools[slot_num] = created_spool
            created.append(
                {
                    "slot": slot_num,
                    "spool_id": created_spool.id,
                    "source": "auto_created_from_cfs",
                    "replaced_spool_id": previous_spool_id,
                }
            )
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
        delta_g = round(new_weight - old_weight, 1)
        consumed_g = round(max(0.0, old_weight - new_weight), 1)
        changed = abs(delta_g) >= SYNC_CHANGE_THRESHOLD_G
        updated.append(
            {
                "slot": slot_num,
                "key": slot_data["key"],
                "spool_id": spool.id,
                "old_g": old_weight,
                "new_g": new_weight,
                "delta_g": delta_g,
                "consumed_g": consumed_g,
                "changed": changed,
                "raw_k2_g": raw_k2_g,
                "applied_factor": applied_factor,
                "source": "k2_calibrated" if applied_factor is not None else "k2_raw",
            }
        )

    db.commit()
    changed_updates = [entry for entry in updated if entry["changed"]]
    return {
        "synced": len(changed_updates),
        "unchanged": len(updated) - len(changed_updates),
        "updates": updated,
        "changed_updates": changed_updates,
        "created_count": len(created),
        "created": created,
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
