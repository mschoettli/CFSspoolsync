import re

from fastapi import APIRouter, File, UploadFile

from app.core.config import settings

router = APIRouter(prefix="/api/ocr", tags=["ocr"])


@router.post("/scan")
async def scan_label(file: UploadFile = File(...)) -> dict:
    data = await file.read()
    text = data.decode("utf-8", errors="ignore")[:4000]

    material_match = re.search(r"\b(PLA|PETG|ABS|ASA|TPU|PA|NYLON)\b", text, flags=re.IGNORECASE)
    weight_match = re.search(r"(\d{2,4})\s*(g|kg)", text, flags=re.IGNORECASE)

    material = material_match.group(1).upper() if material_match else ""
    weight_g = None
    if weight_match:
        value = float(weight_match.group(1))
        unit = weight_match.group(2).lower()
        weight_g = value * 1000.0 if unit == "kg" else value

    warnings = []
    if not material:
        warnings.append("material_not_detected")
    if weight_g is None:
        warnings.append("weight_not_detected")

    provider_chain = ["local-regex"]
    fallback_reason = None
    cloud_used = False

    if settings.ocr_enable_cloud_fallback and warnings and (settings.openai_api_key or settings.anthropic_api_key):
        provider_chain.append("cloud-configured")
        fallback_reason = "cloud_fallback_not_implemented_in_module_v1"

    return {
        "engine": "local-regex",
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
