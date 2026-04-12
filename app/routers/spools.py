"""HTTP routes for spool management."""

import asyncio
from datetime import datetime, timezone
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Spool
from app.schemas.spool import (
    SpoolCalibrationIn,
    SpoolCalibrationOut,
    SpoolCreate,
    SpoolOut,
    SpoolUpdate,
)
from app.services import ssh_client
from app.services.spool_defaults import get_default_tare_weight_g

router = APIRouter(prefix="/api/spools", tags=["spools"])

MIN_CALIBRATION_FACTOR = float(os.getenv("CALIBRATION_FACTOR_MIN", "0.1"))
MAX_CALIBRATION_FACTOR = float(os.getenv("CALIBRATION_FACTOR_MAX", "12.0"))


@router.get("", response_model=list[SpoolOut])
def list_spools(
    status: Optional[str] = Query(None, description="lager|aktiv|leer"),
    db: Session = Depends(get_db),
):
    """List spools and optionally filter by status."""
    query = db.query(Spool)
    if status:
        query = query.filter(Spool.status == status)
    return query.order_by(Spool.updated_at.desc()).all()


@router.post("", response_model=SpoolOut, status_code=201)
def create_spool(payload: SpoolCreate, db: Session = Depends(get_db)):
    """Create a spool entry in storage."""
    data = payload.model_dump()
    gross_weight = data.pop("gross_weight_g", None)
    remaining = data.pop("remaining_weight")
    requested_status = data.pop("status")
    requested_slot = data.pop("cfs_slot")

    if data.get("tare_weight_g") is None:
        data["tare_weight_g"] = get_default_tare_weight_g(
            data.get("brand"),
            data.get("material"),
        )
    tare_weight = data.get("tare_weight_g") or 0.0

    if gross_weight is not None:
        if gross_weight < tare_weight:
            raise HTTPException(422, "Bruttogewicht darf nicht kleiner als Tara sein")
        net_weight = round(max(0.0, gross_weight - tare_weight), 1)
        if net_weight <= 0:
            raise HTTPException(422, "Berechnetes Nettogewicht muss > 0 sein")
        data["initial_weight"] = net_weight
        remaining = net_weight
        data["last_gross_weight_g"] = round(gross_weight, 1)
        data["tare_weight_g"] = round(tare_weight, 1)
    else:
        if data.get("initial_weight") is None:
            raise HTTPException(422, "Anfangsgewicht ist erforderlich")
        if remaining is None:
            remaining = data["initial_weight"]

    status = requested_status or ("aktiv" if requested_slot is not None else "lager")
    cfs_slot = requested_slot if status == "aktiv" else None

    if status == "aktiv" and cfs_slot is None:
        raise HTTPException(422, "cfs_slot ist erforderlich fuer aktive Spulen")
    if cfs_slot is not None:
        occupied = (
            db.query(Spool)
            .filter(Spool.status == "aktiv", Spool.cfs_slot == cfs_slot)
            .first()
        )
        if occupied:
            raise HTTPException(409, f"Slot {cfs_slot} ist bereits belegt")

    spool = Spool(
        **data,
        remaining_weight=remaining,
        status=status,
        cfs_slot=cfs_slot,
    )
    db.add(spool)
    db.commit()
    db.refresh(spool)
    return spool


@router.get("/{spool_id}", response_model=SpoolOut)
def get_spool(spool_id: int, db: Session = Depends(get_db)):
    """Return one spool by identifier."""
    spool = db.query(Spool).filter(Spool.id == spool_id).first()
    if not spool:
        raise HTTPException(404, "Spule nicht gefunden")
    return spool


@router.put("/{spool_id}", response_model=SpoolOut)
def update_spool(spool_id: int, payload: SpoolUpdate, db: Session = Depends(get_db)):
    """Update mutable fields of a spool."""
    spool = db.query(Spool).filter(Spool.id == spool_id).first()
    if not spool:
        raise HTTPException(404, "Spule nicht gefunden")

    updates = payload.model_dump(exclude_none=True)
    new_initial = updates.get("initial_weight", spool.initial_weight)
    new_remaining = updates.get("remaining_weight", spool.remaining_weight)
    new_nozzle_min = updates.get("nozzle_min", spool.nozzle_min)
    new_nozzle_max = updates.get("nozzle_max", spool.nozzle_max)

    if new_remaining > new_initial:
        raise HTTPException(422, "remaining_weight darf nicht groesser als initial_weight sein")
    if new_nozzle_min > new_nozzle_max:
        raise HTTPException(422, "nozzle_min darf nicht groesser als nozzle_max sein")

    for field, value in updates.items():
        setattr(spool, field, value)
    spool.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

    db.commit()
    db.refresh(spool)
    return spool


@router.delete("/{spool_id}")
def delete_spool(spool_id: int, db: Session = Depends(get_db)):
    """Delete a spool that is not assigned to an active CFS slot."""
    spool = db.query(Spool).filter(Spool.id == spool_id).first()
    if not spool:
        raise HTTPException(404, "Spule nicht gefunden")
    if spool.status == "aktiv":
        raise HTTPException(400, "Aktive Spule zuerst aus dem CFS entfernen")

    db.delete(spool)
    db.commit()
    return {"ok": True}


@router.post("/{spool_id}/calibrate-weight", response_model=SpoolCalibrationOut)
async def calibrate_spool_weight(
    spool_id: int,
    payload: SpoolCalibrationIn,
    db: Session = Depends(get_db),
):
    """Calibrate one spool using gross and tare scale readings."""
    spool = db.query(Spool).filter(Spool.id == spool_id).first()
    if not spool:
        raise HTTPException(404, "Spule nicht gefunden")

    tare_weight = payload.tare_weight_g
    if tare_weight is None:
        tare_weight = (
            spool.tare_weight_g
            if spool.tare_weight_g is not None
            else (
                get_default_tare_weight_g(spool.brand, spool.material)
                or 0.0
            )
        )
    gross_weight = payload.gross_weight_g
    if gross_weight < tare_weight:
        raise HTTPException(422, "Bruttogewicht darf nicht kleiner als Tara sein")

    net_measured = round(max(0.0, gross_weight - tare_weight), 1)
    raw_k2_g: Optional[float] = None
    factor = spool.calibration_factor

    if spool.status == "aktiv" and spool.cfs_slot in (1, 2, 3, 4):
        slot_data = await asyncio.to_thread(ssh_client.get_slot, spool.cfs_slot)
        if slot_data and slot_data.get("loaded"):
            raw_k2_g = round(
                ssh_client.meters_to_grams(
                    slot_data.get("remain_len", 0),
                    spool.diameter,
                    spool.density,
                ),
                1,
            )
            if raw_k2_g > 0:
                candidate = net_measured / raw_k2_g
                if candidate < MIN_CALIBRATION_FACTOR or candidate > MAX_CALIBRATION_FACTOR:
                    raise HTTPException(
                        422,
                        (
                            "Kalibrierfaktor ausserhalb erlaubtem Bereich "
                            f"({MIN_CALIBRATION_FACTOR}..{MAX_CALIBRATION_FACTOR})"
                        ),
                    )
                factor = round(candidate, 4)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    spool.tare_weight_g = round(tare_weight, 1)
    spool.last_gross_weight_g = round(gross_weight, 1)
    spool.remaining_weight = min(net_measured, spool.initial_weight)
    spool.calibration_factor = factor
    spool.calibrated_at = now
    spool.updated_at = now

    db.commit()
    db.refresh(spool)
    return {
        "spool_id": spool.id,
        "remaining_weight": spool.remaining_weight,
        "raw_k2_g": raw_k2_g,
        "calibration_factor": spool.calibration_factor,
        "calibrated_at": spool.calibrated_at,
    }


@router.post("/defaults/apply-brand")
def apply_brand_defaults(db: Session = Depends(get_db)):
    """Apply known brand default tare weights to unconfigured spools.

    Args:
    -----
        db (Session):
            Active SQLAlchemy session.

    Returns:
    --------
        dict[str, object]:
            Number of updated spools and changed entries.
    """
    changed = []
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    spools = db.query(Spool).all()
    for spool in spools:
        if spool.tare_weight_g is not None:
            continue
        default_tare = get_default_tare_weight_g(spool.brand, spool.material)
        if default_tare is None:
            continue
        spool.tare_weight_g = default_tare
        spool.updated_at = now
        changed.append(
            {
                "spool_id": spool.id,
                "brand": spool.brand,
                "material": spool.material,
                "tare_weight_g": default_tare,
            }
        )

    db.commit()
    return {"updated": len(changed), "entries": changed}
