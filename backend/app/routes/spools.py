"""CRUD fÃ¼r Spulen."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Slot, Spool
from ..schemas import SpoolCreate, SpoolOut, SpoolUpdate

router = APIRouter(prefix="/spools", tags=["spools"])


def _has_text_value(value: str | None) -> bool:
    """Return True when the value contains non-whitespace characters."""
    return bool((value or "").strip())


def _sanitize_spool(spool: Spool) -> bool:
    """Force legacy rows into API-safe values expected by SpoolOut."""
    changed = False

    if not _has_text_value(spool.manufacturer):
        spool.manufacturer = (spool.material or "Unknown").strip() or "Unknown"
        changed = True
    if not _has_text_value(spool.material):
        spool.material = "Unknown"
        changed = True
    if not _has_text_value(spool.color):
        spool.color = "Unknown"
        changed = True
    if not _has_text_value(spool.color_hex):
        spool.color_hex = "#22c55e"
        changed = True
    if spool.diameter is None or float(spool.diameter) < 1.0 or float(spool.diameter) > 4.0:
        spool.diameter = 1.75
        changed = True
    if spool.nozzle_temp is None or int(spool.nozzle_temp) < 150 or int(spool.nozzle_temp) > 350:
        spool.nozzle_temp = 210
        changed = True
    if spool.bed_temp is None or int(spool.bed_temp) < 0 or int(spool.bed_temp) > 150:
        spool.bed_temp = 60
        changed = True
    if spool.tare_weight is None or float(spool.tare_weight) < 0:
        spool.tare_weight = 0
        changed = True
    if spool.gross_weight is None or float(spool.gross_weight) <= 0:
        spool.gross_weight = max(1.0, float(spool.tare_weight or 0.0) + 1.0)
        changed = True
    if spool.initial_remain_pct is not None and (
        float(spool.initial_remain_pct) < 0 or float(spool.initial_remain_pct) > 100
    ):
        spool.initial_remain_pct = None
        changed = True

    return changed


@router.get("", response_model=list[SpoolOut])
def list_spools(db: Session = Depends(get_db)):
    spools = db.query(Spool).order_by(Spool.manufacturer, Spool.material).all()
    changed = False
    for spool in spools:
        if _sanitize_spool(spool):
            changed = True
    if changed:
        db.commit()
    return spools


@router.post("", response_model=SpoolOut, status_code=201)
def create_spool(payload: SpoolCreate, db: Session = Depends(get_db)):
    data = payload.model_dump(exclude={"assign_to_slot"}, exclude_none=True)
    if "color" in data:
        data["color"] = data["color"].strip()
    if "color_hex" in data:
        data["color_hex"] = data["color_hex"].strip().upper()

    if not _has_text_value(data.get("color")) and not _has_text_value(data.get("color_hex")):
        raise HTTPException(status_code=422, detail="Either 'color' or 'color_hex' must be provided.")

    data["color"] = data.get("color", "")
    data["color_hex"] = data.get("color_hex", "")
    spool = Spool(**data)
    db.add(spool)
    db.commit()
    db.refresh(spool)

    # optionally assign directly to a slot
    if payload.assign_to_slot:
        slot = db.query(Slot).get(payload.assign_to_slot)
        if not slot:
            raise HTTPException(400, "UngÃ¼ltiger Slot")
        slot.spool_id = spool.id
        slot.current_weight = spool.gross_weight
        slot.weight_mode = "cfs_live"
        slot.is_printing = False
        slot.flow = 0
        db.commit()

    return spool


@router.get("/{spool_id}", response_model=SpoolOut)
def get_spool(spool_id: int, db: Session = Depends(get_db)):
    spool = db.query(Spool).get(spool_id)
    if not spool:
        raise HTTPException(404, "Spule nicht gefunden")
    if _sanitize_spool(spool):
        db.commit()
        db.refresh(spool)
    return spool


@router.patch("/{spool_id}", response_model=SpoolOut)
def update_spool(spool_id: int, payload: SpoolUpdate, db: Session = Depends(get_db)):
    spool = db.query(Spool).get(spool_id)
    if not spool:
        raise HTTPException(404, "Spule nicht gefunden")

    data = payload.model_dump(exclude_unset=True)
    if "color" in data:
        data["color"] = (data["color"] or "").strip()
    if "color_hex" in data:
        data["color_hex"] = (data["color_hex"] or "").strip().upper()

    for k, v in data.items():
        setattr(spool, k, v)

    if not _has_text_value(spool.color) and not _has_text_value(spool.color_hex):
        raise HTTPException(status_code=422, detail="Either 'color' or 'color_hex' must be provided.")
    _sanitize_spool(spool)

    db.commit()
    db.refresh(spool)

    return spool


@router.delete("/{spool_id}", status_code=204)
def delete_spool(spool_id: int, db: Session = Depends(get_db)):
    spool = db.query(Spool).get(spool_id)
    if not spool:
        raise HTTPException(404, "Spule nicht gefunden")
    # Remove slot reference
    slot = db.query(Slot).filter(Slot.spool_id == spool_id).first()
    if slot:
        slot.spool_id = None
        slot.current_weight = 0
        slot.weight_mode = "cfs_live"
        slot.is_printing = False
        slot.flow = 0
    db.delete(spool)
    db.commit()
    return None

