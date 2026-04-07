"""HTTP routes for label OCR parsing."""

import asyncio

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.services.label_ocr import ocr_image, parse_label

router = APIRouter(prefix="/api", tags=["ocr"])


@router.post("/scan-label")
async def scan_label(file: UploadFile = File(...)):
    """Extract filament information from an uploaded spool-label image."""
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(400, "Bild zu gross (max 10 MB)")

    text = await asyncio.to_thread(ocr_image, content)
    if text is None:
        raise HTTPException(503, "OCR fehlgeschlagen – Tesseract nicht verfügbar")

    return parse_label(text)
