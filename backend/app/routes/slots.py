"""Slot actions for assignment, unassignment, and CFS snapshots."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import CfsSlotSnapshot, CfsState, Slot, Spool
from ..schemas import CfsSnapshotOut, SlotAdoptAmount, SlotAssign, SlotOut

router = APIRouter(prefix="/slots", tags=["slots"])


def _snapshot_has_rfid_signal(snap: CfsSlotSnapshot | None) -> bool:
    if snap is None:
        return False
    if snap.present:
        return True
    if snap.remain_pct is not None:
        return True
    if (snap.material_code or "").strip() not in ("", "-1", "0", "None"):
        return True
    if (snap.color_hex or "").strip() not in ("", "#6b7280"):
        return True
    if (snap.manufacturer or "").strip() or (snap.material or "").strip():
        return True
    return False


def _attach_snapshot(slot: Slot, db: Session) -> Slot:
    """Attach CFS snapshot and sync status fields to slot ORM instance."""
    snap = db.query(CfsSlotSnapshot).get(slot.id)
    cfs_state = db.query(CfsState).first()
    connected = bool(cfs_state and cfs_state.connected)
    slot.cfs_snapshot = snap  # type: ignore[attr-defined]
    has_signal = _snapshot_has_rfid_signal(snap)
    if slot.spool_id and not has_signal:
        status = "red"
        reason = "No RFID detected in slot"
    elif slot.spool_id and has_signal:
        status = "green"
        reason = None
    elif not connected:
        status = "red"
        reason = "CFS disconnected"
    else:
        status = "green"
        reason = None
    slot.sync_status = status  # type: ignore[attr-defined]
    slot.sync_reason = reason  # type: ignore[attr-defined]
    return slot


def _sanitize_spool_for_slot(spool: Spool) -> bool:
    """Keep nested spool payload in SlotOut schema-safe."""
    changed = False
    if not (spool.manufacturer or "").strip():
        spool.manufacturer = (spool.material or "Unknown").strip() or "Unknown"
        changed = True
    if not (spool.material or "").strip():
        spool.material = "Unknown"
        changed = True
    if not (spool.color or "").strip():
        spool.color = "Unknown"
        changed = True
    if not (spool.color_hex or "").strip():
        spool.color_hex = "#22c55e"
        changed = True
    if spool.gross_weight is None or float(spool.gross_weight) <= 0:
        spool.gross_weight = max(1.0, float(spool.tare_weight or 0.0) + 1.0)
        changed = True
    if spool.tare_weight is None or float(spool.tare_weight) < 0:
        spool.tare_weight = 0
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
    return changed


def _apply_snapshot_to_spool(spool: Spool, snap: CfsSlotSnapshot) -> None:
    """Overwrite spool metadata with RFID snapshot values."""
    if snap.color_hex:
        spool.color_hex = snap.color_hex
        spool.color = snap.color_hex
    if snap.nozzle_temp is not None:
        spool.nozzle_temp = int(snap.nozzle_temp)
    if snap.bed_temp is not None:
        spool.bed_temp = int(snap.bed_temp)


@router.get("", response_model=list[SlotOut])
def list_slots(db: Session = Depends(get_db)):
    slots = db.query(Slot).order_by(Slot.id).all()
    changed = False
    for slot in slots:
        if slot.spool and _sanitize_spool_for_slot(slot.spool):
            changed = True
    if changed:
        db.commit()
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
    slot.weight_mode = "cfs_live"
    slot.is_printing = False
    slot.flow = 0

    snap = db.query(CfsSlotSnapshot).get(slot_id)
    if snap and snap.remain_pct is not None and spool.initial_remain_pct is None:
        spool.initial_remain_pct = snap.remain_pct
    if _snapshot_has_rfid_signal(snap):
        _apply_snapshot_to_spool(spool, snap)

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
    slot.weight_mode = "cfs_live"
    slot.is_printing = False
    slot.flow = 0
    db.commit()
    db.refresh(slot)
    return _attach_snapshot(slot, db)


@router.post("/{slot_id}/refresh-rfid", response_model=SlotOut)
def refresh_slot_rfid(slot_id: int, db: Session = Depends(get_db)):
    slot = db.query(Slot).get(slot_id)
    if not slot:
        raise HTTPException(404, "Slot nicht gefunden")
    if not slot.spool_id:
        raise HTTPException(400, "Keine Spule im Slot zugewiesen")

    spool = db.query(Spool).get(slot.spool_id)
    snap = db.query(CfsSlotSnapshot).get(slot_id)
    if spool is None or snap is None:
        raise HTTPException(404, "RFID Snapshot oder Spule nicht gefunden")
    if not _snapshot_has_rfid_signal(snap):
        # Keep UX retry-friendly: no hard API error if RFID signal is currently weak.
        return _attach_snapshot(slot, db)

    _apply_snapshot_to_spool(spool, snap)
    if snap.manufacturer:
        spool.manufacturer = snap.manufacturer
    if snap.material:
        spool.material = snap.material
    elif (snap.material_code or "").strip():
        spool.material = f"Unknown ({(snap.material_code or '').strip()})"
    db.commit()
    db.refresh(slot)
    return _attach_snapshot(slot, db)


@router.post("/{slot_id}/adopt-amount", response_model=SlotOut)
def adopt_slot_amount(slot_id: int, payload: SlotAdoptAmount, db: Session = Depends(get_db)):
    slot = db.query(Slot).get(slot_id)
    if not slot:
        raise HTTPException(404, "Slot nicht gefunden")
    if not slot.spool_id:
        raise HTTPException(400, "Keine Spule im Slot zugewiesen")
    slot.current_weight = float(payload.amount_g)
    slot.weight_mode = "manual_fixed"
    db.commit()
    db.refresh(slot)
    return _attach_snapshot(slot, db)


# ---------- CFS Snapshot endpoint ----------
cfs_slots_router = APIRouter(prefix="/cfs/slots", tags=["cfs"])


@cfs_slots_router.get("", response_model=list[CfsSnapshotOut])
def list_cfs_snapshots(db: Session = Depends(get_db)):
    """Return current CFS detection state for all 4 slots."""
    snaps = db.query(CfsSlotSnapshot).order_by(CfsSlotSnapshot.slot_id).all()
    if not snaps:
        return [
            CfsSnapshotOut(
                slot_id=i,
                present=False,
                known=False,
                material_code=None,
                manufacturer=None,
                material=None,
                nozzle_temp=None,
                bed_temp=None,
                color_hex=None,
                remain_pct=None,
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
            slot_id=slot_id,
            present=False,
            known=False,
            material_code=None,
            manufacturer=None,
            material=None,
            nozzle_temp=None,
            bed_temp=None,
            color_hex=None,
            remain_pct=None,
        )
    return snap
