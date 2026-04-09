"""HTTP routes for OCR v2 label scanning."""

import asyncio
import os

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.services.label_ocr_v2 import run_ocr_v2

router = APIRouter(prefix="/api/ocr/v2", tags=["ocr"])
OCR_TIMEOUT_SECONDS = int(os.getenv("OCR_TIMEOUT_SECONDS", "120"))
OCR_INTERNAL_BUDGET_RATIO = float(os.getenv("OCR_V2_INTERNAL_BUDGET_RATIO", "0.9"))
OCR_DEBUG = os.getenv("OCR_V2_DEBUG", "0") == "1"


@router.post("/scan")
async def scan_label_v2(file: UploadFile = File(...)):
    """Run OCR v2 on an uploaded label image."""
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(400, "Bild zu gross (max 10 MB)")

    try:
        budget_seconds = max(5.0, OCR_TIMEOUT_SECONDS * OCR_INTERNAL_BUDGET_RATIO)
        return await asyncio.wait_for(
            asyncio.to_thread(
                run_ocr_v2,
                content,
                budget_seconds=budget_seconds,
                debug=OCR_DEBUG,
            ),
            timeout=OCR_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError as exc:
        raise HTTPException(504, f"OCR-Analyse Timeout ({OCR_TIMEOUT_SECONDS}s)") from exc
