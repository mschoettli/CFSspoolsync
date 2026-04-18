"""OCR endpoint for filament label scanning."""
from __future__ import annotations

import json
import io
import re
import time
from typing import Any

import httpx
import pytesseract
from fastapi import APIRouter, File, HTTPException, UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError

from ..config import settings

router = APIRouter(prefix="/ocr", tags=["ocr"])

MATERIAL_ALIASES = {
    "PLA": "PLA",
    "PLA+": "PLA+",
    "HYPER PLA": "Hyper PLA",
    "CR-PLA": "CR-PLA",
    "PETG": "PETG",
    "ABS": "ABS",
    "ASA": "ASA",
    "TPU": "TPU",
    "NYLON": "Nylon",
    "PA": "Nylon",
    "PC": "PC",
}


def _extract_with_regex(text: str) -> dict[str, Any]:
    """Extract core spool fields from OCR text."""
    upper = text.upper()
    material = ""
    for key, value in MATERIAL_ALIASES.items():
        if key in upper:
            material = value
            break

    diameter_mm = None
    diameter_match = re.search(r"([123](?:[.,]\d{1,2})?)\s*MM", upper)
    if diameter_match:
        diameter_mm = float(diameter_match.group(1).replace(",", "."))

    weight_g = None
    weight_match = re.search(r"(\d{2,4}(?:[.,]\d+)?)\s*(KG|G)\b", upper)
    if weight_match:
        value = float(weight_match.group(1).replace(",", "."))
        unit = weight_match.group(2)
        weight_g = value * 1000.0 if unit == "KG" else value

    nozzle_min = nozzle_max = None
    nozzle_range = re.search(r"NOZZLE[^0-9]*(\d{3})\s*[-~]\s*(\d{3})", upper)
    if nozzle_range:
        nozzle_min = int(nozzle_range.group(1))
        nozzle_max = int(nozzle_range.group(2))

    bed_min = bed_max = None
    bed_range = re.search(r"BED[^0-9]*(\d{2,3})\s*[-~]\s*(\d{2,3})", upper)
    if bed_range:
        bed_min = int(bed_range.group(1))
        bed_max = int(bed_range.group(2))

    brand = ""
    first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
    if first_line and len(first_line) <= 32:
        brand = first_line.title()

    color_name = ""
    color_match = re.search(r"\b(WHITE|BLACK|RED|BLUE|GREEN|ORANGE|YELLOW|GOLD|SILVER|PINK|PURPLE|GRAY|GREY|BROWN)\b", upper)
    if color_match:
        color_name = color_match.group(1).title().replace("Grey", "Gray")

    return {
        "brand": brand,
        "material": material,
        "color_name": color_name,
        "color_hex": "",
        "diameter_mm": diameter_mm,
        "weight_g": weight_g,
        "nozzle_min": nozzle_min,
        "nozzle_max": nozzle_max,
        "bed_min": bed_min,
        "bed_max": bed_max,
    }


def _llm_prompt(raw_text: str, baseline: dict[str, Any]) -> str:
    """Build a constrained JSON-only extraction prompt."""
    schema = {
        "brand": "",
        "material": "",
        "color_name": "",
        "color_hex": "",
        "diameter_mm": None,
        "weight_g": None,
        "nozzle_min": None,
        "nozzle_max": None,
        "bed_min": None,
        "bed_max": None,
    }
    return (
        "Extract filament spool label values as strict JSON with this schema only:\n"
        f"{json.dumps(schema)}\n"
        "Rules: keep unknown values as null or empty string, do not invent, "
        "normalize material names (PLA, PLA+, PETG, ABS, ASA, TPU, Nylon, PC), "
        "diameter in mm, weight in grams.\n"
        f"Baseline parse: {json.dumps(baseline)}\n"
        f"OCR text:\n{raw_text[:settings.ocr_llm_max_chars]}"
    )


async def _openai_extract(prompt: str) -> dict[str, Any] | None:
    if not settings.openai_api_key:
        return None
    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": settings.ocr_openai_model,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": "Return only JSON."},
            {"role": "user", "content": prompt},
        ],
    }
    async with httpx.AsyncClient(timeout=settings.ocr_cloud_timeout_s) as client:
        response = await client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=body)
        response.raise_for_status()
        payload = response.json()
    content = payload["choices"][0]["message"]["content"]
    return json.loads(content)


async def _anthropic_extract(prompt: str) -> dict[str, Any] | None:
    if not settings.anthropic_api_key:
        return None
    headers = {
        "x-api-key": settings.anthropic_api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    body = {
        "model": settings.ocr_anthropic_model,
        "max_tokens": 700,
        "temperature": 0,
        "messages": [{"role": "user", "content": prompt}],
    }
    async with httpx.AsyncClient(timeout=settings.ocr_cloud_timeout_s) as client:
        response = await client.post("https://api.anthropic.com/v1/messages", headers=headers, json=body)
        response.raise_for_status()
        payload = response.json()
    content_blocks = payload.get("content", [])
    text = "".join(block.get("text", "") for block in content_blocks if block.get("type") == "text")
    return json.loads(text)


def _merge_result(base: dict[str, Any], candidate: dict[str, Any] | None) -> dict[str, Any]:
    if not candidate:
        return base
    merged = dict(base)
    for key in merged:
        value = candidate.get(key)
        if value not in (None, "", []):
            merged[key] = value
    return merged


@router.post("/scan")
async def scan_label(file: UploadFile = File(...)) -> dict[str, Any]:
    """Scan a filament label image and return structured fields."""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image uploads are supported.")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty upload.")
    if len(data) > settings.ocr_max_upload_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Uploaded image is too large.")

    started = time.perf_counter()
    try:
        image = Image.open(io.BytesIO(data)).convert("RGB")
    except UnidentifiedImageError as exc:
        raise HTTPException(status_code=400, detail="Unsupported image format.") from exc
    image = ImageOps.autocontrast(image)
    gray = ImageOps.grayscale(image)
    raw_text = pytesseract.image_to_string(gray, lang=settings.ocr_tesseract_lang).strip()

    warnings: list[str] = []
    if not raw_text:
        warnings.append("no_text_detected")

    regex_result = _extract_with_regex(raw_text)
    provider_chain: list[str] = ["tesseract+regex"]
    provider_used = "tesseract+regex"
    fallback_reason = None

    result = regex_result
    if settings.ocr_enable_cloud_fallback and raw_text and (settings.openai_api_key or settings.anthropic_api_key):
        prompt = _llm_prompt(raw_text, regex_result)
        try:
            llm_result = await _openai_extract(prompt)
            result = _merge_result(regex_result, llm_result)
            provider_chain.append("openai")
            provider_used = "openai"
        except Exception:
            if settings.anthropic_api_key:
                try:
                    llm_result = await _anthropic_extract(prompt)
                    result = _merge_result(regex_result, llm_result)
                    provider_chain.append("anthropic")
                    provider_used = "anthropic"
                except Exception:
                    fallback_reason = "cloud_extract_failed"
                    warnings.append("cloud_extract_failed")
            else:
                fallback_reason = "openai_failed"
                warnings.append("openai_failed")

    if not result.get("material"):
        warnings.append("material_not_detected")
    if result.get("weight_g") is None:
        warnings.append("weight_not_detected")

    duration_ms = int((time.perf_counter() - started) * 1000)
    return {
        "engine": "tesseract+regex",
        "stub": False,
        "duration_ms": duration_ms,
        "raw_text": raw_text[:settings.ocr_raw_text_limit],
        "warnings": sorted(set(warnings)),
        "result": result,
        "fallback_recommended": bool(warnings),
        "provider_used": provider_used,
        "provider_chain": provider_chain,
        "fallback_reason": fallback_reason,
        "cloud_used": provider_used in ("openai", "anthropic"),
    }
