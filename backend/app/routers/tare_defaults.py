from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import TareDefault

router = APIRouter(prefix="/api/tare-defaults", tags=["tare-defaults"])


class TareDefaultIn(BaseModel):
    brand_key: str
    brand_label: str
    tare_weight_g: float = Field(..., gt=0)


@router.get("")
def list_defaults(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.query(TareDefault).order_by(TareDefault.brand_label.asc()).all()
    return [
        {
            "id": row.id,
            "brand_key": row.brand_key,
            "brand_label": row.brand_label,
            "tare_weight_g": row.tare_weight_g,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }
        for row in rows
    ]


@router.post("")
def create_default(payload: TareDefaultIn, db: Session = Depends(get_db)) -> dict:
    existing = db.query(TareDefault).filter(TareDefault.brand_key == payload.brand_key).first()
    if existing:
        raise HTTPException(status_code=409, detail="brand_key already exists")
    row = TareDefault(
        brand_key=payload.brand_key,
        brand_label=payload.brand_label,
        tare_weight_g=payload.tare_weight_g,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {
        "id": row.id,
        "brand_key": row.brand_key,
        "brand_label": row.brand_label,
        "tare_weight_g": row.tare_weight_g,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


@router.delete("/{row_id}")
def delete_default(row_id: int, db: Session = Depends(get_db)) -> dict:
    row = db.query(TareDefault).filter(TareDefault.id == row_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="not found")
    db.delete(row)
    db.commit()
    return {"ok": True}
