"""CRUD für Leerspulen-Gewichte (Tara)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Tare
from ..schemas import TareCreate, TareOut, TareUpdate

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


@router.patch("/{tare_id}", response_model=TareOut)
def update_tare(tare_id: int, payload: TareUpdate, db: Session = Depends(get_db)):
    tare = db.query(Tare).get(tare_id)
    if not tare:
        raise HTTPException(404, "Tara-Eintrag nicht gefunden")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(tare, k, v)
    db.commit()
    db.refresh(tare)
    return tare


@router.delete("/{tare_id}", status_code=204)
def delete_tare(tare_id: int, db: Session = Depends(get_db)):
    tare = db.query(Tare).get(tare_id)
    if not tare:
        raise HTTPException(404, "Tara-Eintrag nicht gefunden")
    db.delete(tare)
    db.commit()
    return None
