"""Slot-Aktionen: Spule zuweisen/entfernen, Druck starten/stoppen."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Slot, Spool
from ..schemas import SlotAssign, SlotOut, SlotPrintToggle

router = APIRouter(prefix="/slots", tags=["slots"])


@router.get("", response_model=list[SlotOut])
def list_slots(db: Session = Depends(get_db)):
    return db.query(Slot).order_by(Slot.id).all()


@router.post("/{slot_id}/assign", response_model=SlotOut)
def assign_spool(slot_id: int, payload: SlotAssign, db: Session = Depends(get_db)):
    slot = db.query(Slot).get(slot_id)
    if not slot:
        raise HTTPException(404, "Slot nicht gefunden")
    spool = db.query(Spool).get(payload.spool_id)
    if not spool:
        raise HTTPException(404, "Spule nicht gefunden")

    # Falls die Spule bereits in einem anderen Slot liegt → dort entfernen
    other = db.query(Slot).filter(Slot.spool_id == spool.id, Slot.id != slot_id).first()
    if other:
        other.spool_id = None
        other.current_weight = 0
        other.is_printing = False
        other.flow = 0

    slot.spool_id = spool.id
    slot.current_weight = spool.gross_weight
    slot.is_printing = False
    slot.flow = 0
    db.commit()
    db.refresh(slot)
    return slot


@router.post("/{slot_id}/unassign", response_model=SlotOut)
def unassign(slot_id: int, db: Session = Depends(get_db)):
    slot = db.query(Slot).get(slot_id)
    if not slot:
        raise HTTPException(404, "Slot nicht gefunden")
    slot.spool_id = None
    slot.current_weight = 0
    slot.is_printing = False
    slot.flow = 0
    db.commit()
    db.refresh(slot)
    return slot


@router.post("/{slot_id}/print", response_model=SlotOut)
def toggle_print(slot_id: int, payload: SlotPrintToggle, db: Session = Depends(get_db)):
    slot = db.query(Slot).get(slot_id)
    if not slot:
        raise HTTPException(404, "Slot nicht gefunden")
    if payload.is_printing and not slot.spool_id:
        raise HTTPException(400, "Slot ist leer — keine Spule zugewiesen")
    slot.is_printing = payload.is_printing
    if not payload.is_printing:
        slot.flow = 0
    db.commit()
    db.refresh(slot)
    return slot
