"""HTTP routes for label OCR parsing."""

import asyncio

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Spool
from app.services.label_ocr import apply_db_similarity_matching, ocr_image, parse_label

router = APIRouter(prefix="/api", tags=["ocr"])


@router.post("/scan-label")
async def scan_label(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Extract filament information from an uploaded spool-label image."""
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(400, "Bild zu gross (max 10 MB)")

    text = await asyncio.to_thread(ocr_image, content)
    if text is None:
        raise HTTPException(503, "OCR fehlgeschlagen – Tesseract nicht verfügbar")

    parsed = parse_label(text)

    spool_rows = db.query(Spool.brand, Spool.material, Spool.color).all()
    db_brands = sorted(
        {
            value.strip()
            for value, _, _ in spool_rows
            if isinstance(value, str) and value.strip()
        }
    )
    db_materials = sorted(
        {
            value.strip()
            for _, value, _ in spool_rows
            if isinstance(value, str) and value.strip()
        }
    )

    color_hex_to_name = {
        "#FFFFFF": "White",
        "#000000": "Black",
        "#FF0000": "Red",
        "#0000FF": "Blue",
        "#00AA00": "Green",
        "#50C878": "Emerald",
        "#FFFF00": "Yellow",
        "#FF8800": "Orange",
        "#880088": "Purple",
        "#888888": "Gray",
        "#C0C0C0": "Silver",
        "#FFD700": "Gold",
        "#8B4513": "Brown",
        "#FF69B4": "Pink",
        "#00CCCC": "Cyan",
        "#CC00CC": "Magenta",
        "#F5DEB3": "Natural",
        "#CCCCCC": "Transparent",
    }
    db_color_names = sorted(
        {
            color_hex_to_name.get(color.strip().upper(), "")
            for _, _, color in spool_rows
            if isinstance(color, str) and color.strip()
        }
    )
    db_color_names = [name for name in db_color_names if name]

    return apply_db_similarity_matching(
        parsed=parsed,
        db_brands=db_brands,
        db_materials=db_materials,
        db_color_names=db_color_names,
    )
