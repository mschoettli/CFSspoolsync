"""HTTP routes for CFS slot data and slot assignment."""

import asyncio
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Spool
from app.schemas.spool import SpoolOut
from app.services import remaining_weight_service, ssh_client
from app.services.spool_defaults import get_default_tare_weight_g

router = APIRouter(prefix="/api/cfs", tags=["cfs"])
CFS_REPLACE_REMAINLEN_JUMP_M = float(os.getenv("CFS_REPLACE_REMAINLEN_JUMP_M", "30"))


def _normalize_text(value: object) -> str:
    """Normalize free-text metadata for stable comparisons."""
    return str(value or "").strip().lower()


def _grams_to_meters(grams: float, diameter_mm: float, density: float) -> float:
    """Inverse conversion of meters_to_grams used for remain-length heuristics."""
    if grams <= 0 or diameter_mm <= 0 or density <= 0:
        return 0.0

    grams_per_meter = ssh_client.meters_to_grams(1.0, diameter_mm, density)
    if grams_per_meter <= 0:
        return 0.0
    return (grams / grams_per_meter) / max(remaining_weight_service.CFS_REMAINLEN_MULTIPLIER, 1e-9)


def _fingerprint_changed(slot_data: dict, spool: Spool) -> bool:
    """Return True if core spool fingerprint changed in a meaningful way."""
    core_fields = ("material", "brand", "name")
    changed = 0

    for field in core_fields:
        live_value = _normalize_text(slot_data.get(field))
        known_value = _normalize_text(getattr(spool, field, ""))
        if not live_value or not known_value:
            continue
        if live_value != known_value:
            changed += 1

    if changed > 0:
        return True

    # Color is supplemental only and should not trigger replacement on its own.
    return False


def _detect_replacement(slot_data: dict, spool: Spool) -> str | None:
    """Detect spool replacement and return a normalized reason code."""
    live_serial = str(slot_data.get("serial_num") or "").strip()
    known_serial = str(spool.serial_num or "").strip()
    if live_serial and known_serial and live_serial != known_serial:
        return "serial_change"

    live_remain_len = float(slot_data.get("remain_len") or 0.0)
    estimated_old_len = _grams_to_meters(
        float(spool.remaining_weight or 0.0),
        float(spool.diameter or 0.0),
        float(spool.density or 0.0),
    )
    remain_len_jump = live_remain_len - estimated_old_len
    if remain_len_jump >= CFS_REPLACE_REMAINLEN_JUMP_M:
        return "remainlen_jump"

    if _fingerprint_changed(slot_data, spool):
        return "fingerprint_change"
    return None


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

    remain_len = float(slot_data.get("remain_len") or 0.0)
    normalized_remain_len = remain_len * remaining_weight_service.CFS_REMAINLEN_MULTIPLIER
    remaining_weight = round(
        max(
            0.0,
            ssh_client.meters_to_grams(normalized_remain_len, diameter, density),
        ),
        1,
    )
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
        last_raw_k2_g=remaining_weight,
        last_raw_remain_len=round(remain_len, 3),
        last_normalized_remain_len=round(normalized_remain_len, 3),
        last_weight_source=remaining_weight_service.SOURCE_K2_LIVE_SYNC,
        last_weight_updated_at=now,
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
    replaced_slots: set[int] = set()
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

        replacement_reason = _detect_replacement(slot_data, spool)
        if replacement_reason and slot_num not in replaced_slots:
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
                    "replacement_reason": replacement_reason,
                }
            )

            created_spool = _create_spool_from_slot(slot_num, slot_data, db, now)
            active_spools[slot_num] = created_spool
            replaced_slots.add(slot_num)
            created.append(
                {
                    "slot": slot_num,
                    "spool_id": created_spool.id,
                    "source": "auto_created_from_cfs",
                    "replaced_spool_id": previous_spool_id,
                    "replacement_reason": replacement_reason,
                }
            )
            continue

        if spool.tare_weight_g is None:
            default_tare = get_default_tare_weight_g(spool.brand, spool.material, db)
            if default_tare is not None:
                spool.tare_weight_g = default_tare

        result = remaining_weight_service.apply_from_k2_remain_len(
            spool=spool,
            remain_len=float(slot_data.get("remain_len") or 0.0),
            source=remaining_weight_service.SOURCE_K2_LIVE_SYNC,
            now=now,
        )
        delta_g = round(result.new_weight - result.old_weight, 1)
        consumed_g = round(max(0.0, result.old_weight - result.new_weight), 1)
        updated.append(
            {
                "slot": slot_num,
                "key": slot_data["key"],
                "spool_id": spool.id,
                "old_g": result.old_weight,
                "new_g": result.new_weight,
                "delta_g": delta_g,
                "consumed_g": consumed_g,
                "changed": result.changed,
                "raw_remain_len": result.raw_remain_len,
                "normalized_remain_len": result.normalized_remain_len,
                "raw_k2_g": result.raw_k2_g,
                "effective_g": result.effective_g,
                "applied_factor": result.applied_factor,
                "source": result.source,
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
