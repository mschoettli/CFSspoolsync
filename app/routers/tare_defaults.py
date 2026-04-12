"""HTTP routes for editable brand default tare values."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import TareDefault
from app.schemas.tare_default import (
    TareDefaultCreate,
    TareDefaultOut,
    TareDefaultUpdate,
)
from app.services.spool_defaults import normalize_brand

router = APIRouter(prefix="/api/tare-defaults", tags=["tare-defaults"])


@router.get("", response_model=list[TareDefaultOut])
def list_tare_defaults(db: Session = Depends(get_db)):
    """Return all configured brand tare defaults."""
    entries = db.query(TareDefault).order_by(TareDefault.brand_label.asc()).all()
    return [
        TareDefaultOut(
            brand_key=entry.brand_key,
            brand_label=entry.brand_label,
            tare_weight_g=entry.tare_weight_g,
            is_system=bool(entry.is_system),
            updated_at=entry.updated_at,
        )
        for entry in entries
    ]


@router.post("", response_model=TareDefaultOut, status_code=201)
def create_tare_default(payload: TareDefaultCreate, db: Session = Depends(get_db)):
    """Create one brand tare default entry."""
    brand_key = normalize_brand(payload.brand_label)
    if not brand_key:
        raise HTTPException(422, "Hersteller darf nicht leer sein")
    existing = db.query(TareDefault).filter(TareDefault.brand_key == brand_key).first()
    if existing:
        raise HTTPException(409, "Hersteller-Default existiert bereits")

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    entry = TareDefault(
        brand_key=brand_key,
        brand_label=payload.brand_label.strip(),
        tare_weight_g=round(payload.tare_weight_g, 1),
        is_system=False,
        updated_at=now,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return TareDefaultOut(
        brand_key=entry.brand_key,
        brand_label=entry.brand_label,
        tare_weight_g=entry.tare_weight_g,
        is_system=bool(entry.is_system),
        updated_at=entry.updated_at,
    )


@router.put("/{brand_key}", response_model=TareDefaultOut)
def update_tare_default(
    brand_key: str,
    payload: TareDefaultUpdate,
    db: Session = Depends(get_db),
):
    """Update one existing brand tare default entry."""
    normalized_key = normalize_brand(brand_key)
    entry = db.query(TareDefault).filter(TareDefault.brand_key == normalized_key).first()
    if not entry:
        raise HTTPException(404, "Hersteller-Default nicht gefunden")

    new_brand_key = normalize_brand(payload.brand_label)
    if not new_brand_key:
        raise HTTPException(422, "Hersteller darf nicht leer sein")
    existing = (
        db.query(TareDefault)
        .filter(TareDefault.brand_key == new_brand_key, TareDefault.id != entry.id)
        .first()
    )
    if existing:
        raise HTTPException(409, "Hersteller-Default existiert bereits")

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    entry.brand_key = new_brand_key
    entry.brand_label = payload.brand_label.strip()
    entry.tare_weight_g = round(payload.tare_weight_g, 1)
    entry.updated_at = now
    db.commit()
    db.refresh(entry)
    return TareDefaultOut(
        brand_key=entry.brand_key,
        brand_label=entry.brand_label,
        tare_weight_g=entry.tare_weight_g,
        is_system=bool(entry.is_system),
        updated_at=entry.updated_at,
    )


@router.delete("/{brand_key}")
def delete_tare_default(brand_key: str, db: Session = Depends(get_db)):
    """Delete one non-system tare default entry."""
    normalized_key = normalize_brand(brand_key)
    entry = db.query(TareDefault).filter(TareDefault.brand_key == normalized_key).first()
    if not entry:
        raise HTTPException(404, "Hersteller-Default nicht gefunden")
    if entry.is_system:
        raise HTTPException(400, "System-Defaults können nicht gelöscht werden")

    db.delete(entry)
    db.commit()
    return {"ok": True}
