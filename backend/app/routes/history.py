"""Verbrauchs-Historie fÃ¼r Charts im Frontend."""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import HistoryEntry
from ..schemas import CfsStateOut, HistoryOut
from ..models import CfsState

router = APIRouter(prefix="/history", tags=["history"])


@router.get("", response_model=list[HistoryOut])
def get_history(
    days: int = Query(7, ge=1, le=90),
    slot_id: int | None = Query(None, ge=1, le=4),
    db: Session = Depends(get_db),
):
    since = datetime.utcnow() - timedelta(days=days)
    q = db.query(HistoryEntry).filter(HistoryEntry.timestamp >= since)
    if slot_id is not None:
        q = q.filter(HistoryEntry.slot_id == slot_id)
    return q.order_by(HistoryEntry.timestamp.asc()).all()


# CFS snapshot (also used for frontend initial load)
cfs_router = APIRouter(prefix="/cfs", tags=["cfs"])


@cfs_router.get("", response_model=CfsStateOut)
def get_cfs(db: Session = Depends(get_db)):
    state = db.query(CfsState).first()
    if state is None:
        state = CfsState(id=1)
        db.add(state)
        db.commit()
        db.refresh(state)
    return state

