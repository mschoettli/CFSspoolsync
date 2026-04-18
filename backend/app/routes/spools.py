"""CRUD für Spulen."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Slot, Spool
from ..schemas import SpoolCreate, SpoolOut, SpoolUpdate

router = APIRouter(prefix="/spools", tags=["spools"])


@router.get("", response_model=list[SpoolOut])
def list_spools(db: Session = Depends(get_db)):
    return db.query(Spool).order_by(Spool.manufacturer, Spool.material).all()


@router.post("", response_model=SpoolOut, status_code=201)
def create_spool(payload: SpoolCreate, db: Session = Depends(get_db)):
    data = payload.model_dump(exclude={"assign_to_slot"})
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
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(spool, k, v)
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
