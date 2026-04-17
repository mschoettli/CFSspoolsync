from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Spool

router = APIRouter(prefix="/api/spools", tags=["spools"])


class SpoolIn(BaseModel):
    material: str
    color: str = "#888888"
    brand: str = ""
    name: str = ""
    initial_weight: float = Field(..., gt=0)
    remaining_weight: float | None = None
    status: str = "lager"
    cfs_slot: int | None = None
    diameter: float = Field(default=1.75, gt=0)
    density: float = Field(default=1.24, gt=0)


class SpoolPatch(BaseModel):
    material: str | None = None
    color: str | None = None
    brand: str | None = None
    name: str | None = None
    initial_weight: float | None = Field(default=None, gt=0)
    remaining_weight: float | None = Field(default=None, ge=0)
    status: str | None = None
    cfs_slot: int | None = None
    diameter: float | None = Field(default=None, gt=0)
    density: float | None = Field(default=None, gt=0)


def _serialize(spool: Spool) -> dict:
    return {
        "id": spool.id,
        "material": spool.material,
        "color": spool.color,
        "brand": spool.brand,
        "name": spool.name,
        "initial_weight": spool.initial_weight,
        "remaining_weight": spool.remaining_weight,
        "status": spool.status,
        "cfs_slot": spool.cfs_slot,
        "diameter": spool.diameter,
        "density": spool.density,
        "created_at": spool.created_at.isoformat() if spool.created_at else None,
        "updated_at": spool.updated_at.isoformat() if spool.updated_at else None,
    }


@router.get("")
def list_spools(db: Session = Depends(get_db)) -> list[dict]:
    return [_serialize(spool) for spool in db.query(Spool).order_by(Spool.id.desc()).all()]


@router.post("")
def create_spool(payload: SpoolIn, db: Session = Depends(get_db)) -> dict:
    if payload.status == "aktiv" and payload.cfs_slot in (1, 2, 3, 4):
        conflict = (
            db.query(Spool)
            .filter(Spool.status == "aktiv", Spool.cfs_slot == payload.cfs_slot)
            .first()
        )
        if conflict:
            raise HTTPException(status_code=409, detail="CFS slot already occupied")

    spool = Spool(
        material=payload.material,
        color=payload.color,
        brand=payload.brand,
        name=payload.name,
        initial_weight=payload.initial_weight,
        remaining_weight=payload.remaining_weight if payload.remaining_weight is not None else payload.initial_weight,
        status=payload.status,
        cfs_slot=payload.cfs_slot,
        diameter=payload.diameter,
        density=payload.density,
    )
    db.add(spool)
    db.commit()
    db.refresh(spool)
    return _serialize(spool)


@router.put("/{spool_id}")
def update_spool(spool_id: int, payload: SpoolPatch, db: Session = Depends(get_db)) -> dict:
    spool = db.query(Spool).filter(Spool.id == spool_id).first()
    if not spool:
        raise HTTPException(status_code=404, detail="Spool not found")

    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(spool, key, value)

    if spool.status == "aktiv" and spool.cfs_slot in (1, 2, 3, 4):
        conflict = (
            db.query(Spool)
            .filter(Spool.status == "aktiv", Spool.cfs_slot == spool.cfs_slot, Spool.id != spool.id)
            .first()
        )
        if conflict:
            raise HTTPException(status_code=409, detail="CFS slot already occupied")

    db.commit()
    db.refresh(spool)
    return _serialize(spool)


@router.delete("/{spool_id}")
def delete_spool(spool_id: int, db: Session = Depends(get_db)) -> dict:
    spool = db.query(Spool).filter(Spool.id == spool_id).first()
    if not spool:
        raise HTTPException(status_code=404, detail="Spool not found")
    db.delete(spool)
    db.commit()
    return {"ok": True}
