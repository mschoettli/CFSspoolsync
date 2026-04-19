"""CRUD für Spulen."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Slot, Spool
from ..schemas import SpoolCreate, SpoolOut, SpoolUpdate

router = APIRouter(prefix="/spools", tags=["spools"])


def _has_text_value(value: str | None) -> bool:
    """Return True when the value contains non-whitespace characters."""
    return bool((value or "").strip())


@router.get("", response_model=list[SpoolOut])
def list_spools(db: Session = Depends(get_db)):
    return db.query(Spool).order_by(Spool.manufacturer, Spool.material).all()


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

    # optional direkt in einen Slot einlegen
    if payload.assign_to_slot:
        slot = db.query(Slot).get(payload.assign_to_slot)
        if not slot:
            raise HTTPException(400, "Ungültiger Slot")
        slot.spool_id = spool.id
        slot.current_weight = spool.gross_weight
        slot.is_printing = False
        slot.flow = 0
        db.commit()

    return spool


@router.get("/{spool_id}", response_model=SpoolOut)
def get_spool(spool_id: int, db: Session = Depends(get_db)):
    spool = db.query(Spool).get(spool_id)
    if not spool:
        raise HTTPException(404, "Spule nicht gefunden")
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

    db.commit()
    db.refresh(spool)

    # falls diese Spule aktuell eingelegt ist: current_weight synchron halten
    if payload.gross_weight is not None:
        slot = db.query(Slot).filter(Slot.spool_id == spool_id).first()
        if slot:
            slot.current_weight = payload.gross_weight
            db.commit()

    return spool


@router.delete("/{spool_id}", status_code=204)
def delete_spool(spool_id: int, db: Session = Depends(get_db)):
    spool = db.query(Spool).get(spool_id)
    if not spool:
        raise HTTPException(404, "Spule nicht gefunden")
    # Slot-Referenz entfernen
    slot = db.query(Slot).filter(Slot.spool_id == spool_id).first()
    if slot:
        slot.spool_id = None
        slot.current_weight = 0
        slot.is_printing = False
        slot.flow = 0
    db.delete(spool)
    db.commit()
    return None
