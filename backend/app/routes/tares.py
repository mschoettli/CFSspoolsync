"""CRUD for empty spool tare weights."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Spool, Tare
from ..schemas import TareCreate, TareOut, TareUpdate, TareUpdateOut

router = APIRouter(prefix="/tares", tags=["tares"])


@router.get("", response_model=list[TareOut])
def list_tares(db: Session = Depends(get_db)):
    return db.query(Tare).order_by(Tare.manufacturer, Tare.material).all()


@router.post("", response_model=TareOut, status_code=201)
def create_tare(payload: TareCreate, db: Session = Depends(get_db)):
    tare = Tare(**payload.model_dump())
    db.add(tare)
    db.commit()
    db.refresh(tare)
    return tare


@router.patch("/{tare_id}", response_model=TareUpdateOut)
def update_tare(tare_id: int, payload: TareUpdate, db: Session = Depends(get_db)):
    tare = db.query(Tare).get(tare_id)
    if not tare:
        raise HTTPException(404, "Tara-Eintrag nicht gefunden")

    try:
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(tare, key, value)

        normalized_manufacturer = (tare.manufacturer or "").strip().lower()
        normalized_material = (tare.material or "").strip().lower()

        updated_spools_count = (
            db.query(Spool)
            .filter(
                func.lower(func.trim(Spool.manufacturer)) == normalized_manufacturer,
                func.lower(func.trim(Spool.material)) == normalized_material,
            )
            .update({Spool.tare_weight: tare.weight}, synchronize_session=False)
        )

        db.commit()
        db.refresh(tare)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(500, "Tara-Update fehlgeschlagen") from exc

    return {
        "id": tare.id,
        "manufacturer": tare.manufacturer,
        "material": tare.material,
        "weight": tare.weight,
        "updated_spools_count": updated_spools_count,
    }


@router.delete("/{tare_id}", status_code=204)
def delete_tare(tare_id: int, db: Session = Depends(get_db)):
    tare = db.query(Tare).get(tare_id)
    if not tare:
        raise HTTPException(404, "Tara-Eintrag nicht gefunden")
    db.delete(tare)
    db.commit()
    return None
