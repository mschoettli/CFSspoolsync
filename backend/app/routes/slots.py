"""Slot-Aktionen: Spule zuweisen/entfernen, Druck starten/stoppen."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import CfsSlotSnapshot, Slot, Spool
from ..schemas import CfsSnapshotOut, SlotAssign, SlotOut, SlotPrintToggle

router = APIRouter(prefix="/slots", tags=["slots"])


def _attach_snapshot(slot: Slot, db: Session) -> Slot:
    """Pydantic-v2 liest `cfs_snapshot` via from_attributes, wir hängen es an."""
    snap = db.query(CfsSlotSnapshot).get(slot.id)
    slot.cfs_snapshot = snap  # type: ignore[attr-defined]
    return slot


@router.get("", response_model=list[SlotOut])
def list_slots(db: Session = Depends(get_db)):
    slots = db.query(Slot).order_by(Slot.id).all()
    return [_attach_snapshot(s, db) for s in slots]


@router.post("/{slot_id}/assign", response_model=SlotOut)
def assign_spool(slot_id: int, payload: SlotAssign, db: Session = Depends(get_db)):
    slot = db.query(Slot).get(slot_id)
    if not slot:
        raise HTTPException(404, "Slot nicht gefunden")
    spool = db.query(Spool).get(payload.spool_id)
    if not spool:
        raise HTTPException(404, "Spule nicht gefunden")

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

    # Wenn im Moment CFS-Snapshot mit remain_pct existiert, übernehmen wir
    # den als initial_remain_pct falls die Spule noch keinen hat.
    snap = db.query(CfsSlotSnapshot).get(slot_id)
    if snap and snap.remain_pct is not None and spool.initial_remain_pct is None:
        spool.initial_remain_pct = snap.remain_pct

    db.commit()
    db.refresh(slot)
    return _attach_snapshot(slot, db)


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
    return _attach_snapshot(slot, db)


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
    return _attach_snapshot(slot, db)


# ---------- CFS-Snapshot Endpoint ----------
cfs_slots_router = APIRouter(prefix="/cfs/slots", tags=["cfs"])


@cfs_slots_router.get("", response_model=list[CfsSnapshotOut])
def list_cfs_snapshots(db: Session = Depends(get_db)):
    """
    Was das CFS gerade in allen 4 Slots erkennt — unabhängig davon, ob der
    User bereits eine Spule im Lager angelegt hat. Quelle für Auto-Discovery.
    """
    snaps = db.query(CfsSlotSnapshot).order_by(CfsSlotSnapshot.slot_id).all()
    # Falls noch nie gefüllt (frischer Start): 4 leere Einträge zurückgeben
    if not snaps:
        return [
            CfsSnapshotOut(
                slot_id=i, present=False, known=False,
                material_code=None, manufacturer=None, material=None,
                nozzle_temp=None, bed_temp=None, color_hex=None, remain_pct=None,
            )
            for i in range(1, 5)
        ]
    return snaps


@cfs_slots_router.get("/{slot_id}", response_model=CfsSnapshotOut)
def get_cfs_snapshot(slot_id: int, db: Session = Depends(get_db)):
    if slot_id < 1 or slot_id > 4:
        raise HTTPException(400, "Slot-ID muss zwischen 1 und 4 liegen")
    snap = db.query(CfsSlotSnapshot).get(slot_id)
    if snap is None:
        return CfsSnapshotOut(
            slot_id=slot_id, present=False, known=False,
            material_code=None, manufacturer=None, material=None,
            nozzle_temp=None, bed_temp=None, color_hex=None, remain_pct=None,
        )
    return snap
