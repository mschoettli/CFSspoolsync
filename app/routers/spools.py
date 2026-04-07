"""HTTP routes for spool management."""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Spool
from app.schemas.spool import SpoolCreate, SpoolOut, SpoolUpdate

router = APIRouter(prefix="/api/spools", tags=["spools"])


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
    remaining = data.pop("remaining_weight") or data["initial_weight"]
    spool = Spool(**data, remaining_weight=remaining, status="lager")
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

    for field, value in payload.model_dump(exclude_none=True).items():
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
