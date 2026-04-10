"""HTTP routes for OCR label scanning."""

import asyncio
import os

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.services.label_ocr import run_ocr_scan

router = APIRouter(prefix="/api/ocr", tags=["ocr"])
OCR_TIMEOUT_SECONDS = int(os.getenv("OCR_TIMEOUT_SECONDS", "60"))
OCR_CLOUD_TIMEOUT_SECONDS = float(os.getenv("OCR_CLOUD_TIMEOUT_SECONDS", "25"))
OCR_DEBUG = os.getenv("OCR_DEBUG", "0") == "1"
OCR_HTTP_TIMEOUT_SECONDS = float(
    os.getenv(
        "OCR_HTTP_TIMEOUT_SECONDS",
        str(max(OCR_TIMEOUT_SECONDS + (OCR_CLOUD_TIMEOUT_SECONDS * 2) + 5, OCR_TIMEOUT_SECONDS)),
    )
)


@router.post("/scan")
async def scan_label(file: UploadFile = File(...)):
    """Run OCR scan on an uploaded label image."""
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(400, "Bild zu gross (max 10 MB)")

    try:
        return await asyncio.wait_for(
            asyncio.to_thread(
                run_ocr_scan,
                content,
                timeout_seconds=OCR_TIMEOUT_SECONDS,
                debug=OCR_DEBUG,
            ),
            timeout=OCR_HTTP_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError as exc:
        raise HTTPException(504, f"OCR-Analyse Timeout ({OCR_TIMEOUT_SECONDS}s)") from exc
