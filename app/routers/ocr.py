"""HTTP routes for OCR v2 label scanning."""

import asyncio
import os

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.services.label_ocr_v2 import run_ocr_v2

router = APIRouter(prefix="/api/ocr/v2", tags=["ocr"])
OCR_TIMEOUT_SECONDS = int(os.getenv("OCR_TIMEOUT_SECONDS", "120"))


@router.post("/scan")
async def scan_label_v2(file: UploadFile = File(...)):
    """Run OCR v2 on an uploaded label image."""
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(400, "Bild zu gross (max 10 MB)")

    try:
        return await asyncio.wait_for(
            asyncio.to_thread(run_ocr_v2, content),
            timeout=OCR_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError as exc:
        raise HTTPException(504, f"OCR-Analyse Timeout ({OCR_TIMEOUT_SECONDS}s)") from exc
