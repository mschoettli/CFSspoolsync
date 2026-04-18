import asyncio
import re

from fastapi import APIRouter, File, UploadFile

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.runtime_settings import get_setting

router = APIRouter(prefix="/api/ocr", tags=["ocr"])


def _resolve_cloud_keys() -> tuple[str, str]:
    db = SessionLocal()
    try:
        openai_api_key = get_setting(db, "api.openai_key", settings.openai_api_key)
        anthropic_api_key = get_setting(db, "api.anthropic_key", settings.anthropic_api_key)
        return openai_api_key, anthropic_api_key
    finally:
        db.close()


@router.post("/scan")
async def scan_label(file: UploadFile = File(...)) -> dict:
    """Scan label text using the current v1 text-only OCR stub.

    Args:
    -----
        file (UploadFile):
            Uploaded label file.

    Returns:
    --------
        dict:
            Structured OCR-like response with extracted material and weight
            when textual content is provided.
    """
    data = await file.read()
    content_type = (file.content_type or "").lower()
    is_text_input = content_type.startswith("text/") or (file.filename or "").lower().endswith(".txt")
    text = data.decode("utf-8", errors="ignore")[:4000] if is_text_input else ""

    material = ""
    weight_g = None
    if is_text_input:
        material_match = re.search(r"\b(PLA|PETG|ABS|ASA|TPU|PA|NYLON)\b", text, flags=re.IGNORECASE)
        weight_match = re.search(r"(\d{2,4})\s*(g|kg)", text, flags=re.IGNORECASE)
        material = material_match.group(1).upper() if material_match else ""
        if weight_match:
            value = float(weight_match.group(1))
            unit = weight_match.group(2).lower()
            weight_g = value * 1000.0 if unit == "kg" else value

    warnings = []
    if not is_text_input:
        warnings.append("image_ocr_not_implemented")
    elif not material:
        warnings.append("material_not_detected")
    if is_text_input and weight_g is None:
        warnings.append("weight_not_detected")

    openai_api_key, anthropic_api_key = await asyncio.to_thread(_resolve_cloud_keys)

    provider_chain = ["text-regex-stub" if is_text_input else "no-image-ocr"]
    fallback_reason = None
    cloud_used = False

    if settings.ocr_enable_cloud_fallback and warnings and (openai_api_key or anthropic_api_key):
        provider_chain.append("cloud-configured")
        fallback_reason = "cloud_fallback_not_implemented_in_v1"

    return {
        "engine": "text-regex-stub",
        "stub": True,
        "duration_ms": 1,
        "raw_text": text,
        "warnings": warnings,
        "result": {
            "brand": "",
            "material": material,
            "color_name": "",
            "color_hex": "",
            "diameter_mm": None,
            "weight_g": weight_g,
            "nozzle_min": None,
            "nozzle_max": None,
            "bed_min": None,
            "bed_max": None,
        },
        "review": {},
        "fallback_recommended": bool(warnings),
        "suggestions": {"material": [material] if material else [], "brand": [], "color": []},
        "timing": {"total_ms": 1, "partial_timeout": False, "stages": {}},
        "provider_used": provider_chain[-1],
        "provider_chain": provider_chain,
        "fallback_reason": fallback_reason,
        "cloud_used": cloud_used,
    }
