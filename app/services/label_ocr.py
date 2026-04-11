"""OCR pipeline for spool label extraction with provider fallback."""

from __future__ import annotations

import io
import json
import logging
import os
import re
import threading
import time
import unicodedata
import base64
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Optional

import httpx
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

logger = logging.getLogger(__name__)

ACCEPTED_CONFIDENCE = float(os.getenv("OCR_CONFIDENCE_ACCEPTED", "0.8"))
LOW_CONFIDENCE = float(os.getenv("OCR_CONFIDENCE_LOW", "0.55"))
MAX_VARIANTS = max(1, int(os.getenv("OCR_MAX_VARIANTS", "6")))
MAX_IMAGE_BYTES = 10 * 1024 * 1024
OCR_ENABLE_CLOUD_FALLBACK = os.getenv("OCR_ENABLE_CLOUD_FALLBACK", "1") == "1"
OCR_PROVIDER_1 = os.getenv("OCR_PROVIDER_1", "openai").strip().lower()
OCR_PROVIDER_2 = os.getenv("OCR_PROVIDER_2", "claude").strip().lower()
OCR_CLOUD_TIMEOUT_SECONDS = float(os.getenv("OCR_CLOUD_TIMEOUT_SECONDS", "3.5"))
OCR_TOTAL_BUDGET_SECONDS = float(os.getenv("OCR_TOTAL_BUDGET_SECONDS", "15"))
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip()
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest").strip()

COLOR_HEX_MAP = {
    "white": "#FFFFFF",
    "black": "#000000",
    "red": "#FF0000",
    "blue": "#0000FF",
    "green": "#00AA00",
    "emerald": "#50C878",
    "yellow": "#FFFF00",
    "orange": "#FF8800",
    "purple": "#880088",
    "grey": "#888888",
    "gray": "#888888",
    "silver": "#C0C0C0",
    "gold": "#FFD700",
    "brown": "#8B4513",
    "pink": "#FF69B4",
    "cyan": "#00CCCC",
    "magenta": "#CC00CC",
    "natural": "#F5DEB3",
    "transparent": "#CCCCCC",
}

COLOR_ALIASES = {
    "weiss": "white",
    "weiß": "white",
    "schwarz": "black",
    "grau": "gray",
    "golden": "gold",
    "biack": "black",
    "burdy": "brown",
    "burly": "brown",
    "wood": "brown",
    "burdy wood": "brown",
}

COMMON_BRANDS = [
    "JAYO",
    "Geeetech",
    "Creality",
    "Bambu Lab",
    "SUNLU",
    "eSUN",
    "Anycubic",
]

COMMON_MATERIALS = [
    "PLA",
    "PLA+",
    "PETG",
    "ABS",
    "ASA",
    "TPU",
    "PETG-CF",
]

COMMON_COLORS = [
    "White",
    "Black",
    "Gray",
    "Brown",
    "Gold",
    "Blue",
    "Red",
    "Green",
]

MATERIAL_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("PETG-CF", re.compile(r"\bPETG\s*[-+ ]\s*CF\b", re.IGNORECASE)),
    ("PETG-GF", re.compile(r"\bPETG\s*[-+ ]\s*GF\b", re.IGNORECASE)),
    ("PLA+", re.compile(r"\bP[L1I][A4]\s*\+\b", re.IGNORECASE)),
    ("PETG", re.compile(r"\bPETG\b", re.IGNORECASE)),
    ("PLA", re.compile(r"\bP[L1I][A4]\b", re.IGNORECASE)),
    ("ABS", re.compile(r"\bABS\b", re.IGNORECASE)),
    ("ASA", re.compile(r"\bASA\b", re.IGNORECASE)),
    ("TPU", re.compile(r"\bTPU\b", re.IGNORECASE)),
    ("NYLON", re.compile(r"\bNYLON\b", re.IGNORECASE)),
    ("PLA", re.compile(r"\bCR[\s\-]?SILK\b", re.IGNORECASE)),
]

BRAND_PATTERNS: list[tuple[str, re.Pattern[str], float]] = [
    ("Geeetech", re.compile(r"\bGEE+\s*[\+\-]?\s*TECH\b", re.IGNORECASE), 0.99),
    ("Creality", re.compile(r"\bCREALITY\b", re.IGNORECASE), 0.99),
    ("Creality", re.compile(r"\bENDER(?:\s*[- ]?P[L1I][A4])?\b", re.IGNORECASE), 0.92),
    ("JAYO", re.compile(r"\bJAYO\b", re.IGNORECASE), 0.98),
    ("Creality", re.compile(r"\bCR[\s\-]?SILK\b", re.IGNORECASE), 0.85),
]

TESSERACT_CONFIGS = [
    "--oem 3 --psm 6 -l eng",
    "--oem 3 --psm 4 -l eng",
    "--oem 3 --psm 11 -l eng",
    "--oem 1 --psm 6 -l eng",
]

_TESSERACT_LOCK = threading.Lock()
_TESSERACT_READY = False


@dataclass
class ParsedField:
    """Structured parse output for one field."""

    value: object
    confidence: float
    source_text: str
    candidates: list[str]
    rejected: bool = False


@dataclass
class OCRCandidate:
    """Candidate OCR output from one variant/config pair."""

    text: str
    score: float
    variant: str
    config: str


def _normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text or "")
    replacements = {"Â°": "°", "º": "°", "–": "-", "—": "-", "−": "-"}
    for src, dst in replacements.items():
        normalized = normalized.replace(src, dst)
    normalized = re.sub(r"(?<=\d)[Oo](?=\d)", "0", normalized)
    normalized = re.sub(r"(?<=\d)[Il](?=\d)", "1", normalized)
    normalized = re.sub(r"[ \t]+", " ", normalized)
    return normalized.strip()


def _normalize_token(value: str) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKD", value)
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized.lower())
    return re.sub(r"\s+", " ", normalized).strip()


def _score_text(candidate: str) -> float:
    stripped = candidate.strip()
    if not stripped:
        return 0.0
    normalized = _normalize_text(stripped)
    pattern_hits = [
        r"\b(?:PLA|PETG|ABS|ASA|TPU|NYLON)\b",
        r"\b(?:COLOR|FARBE)\b",
        r"\b(?:TEMP|NOZZLE|BED|PRINT)\b",
        r"\b(?:WEIGHT|N\.W\.)\b",
        r"\b(?:MM)\b",
    ]
    hits = sum(bool(re.search(pattern, normalized, re.IGNORECASE)) for pattern in pattern_hits)
    return hits * 30 + min(sum(ch.isalnum() for ch in normalized), 500) * 0.08


def _open_image_from_bytes(image_bytes: bytes) -> Image.Image:
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise ValueError("Image too large")
    try:
        import pillow_heif

        pillow_heif.register_heif_opener()
    except Exception:
        pass
    return Image.open(io.BytesIO(image_bytes))


def _crop_label_region(image: Image.Image) -> Image.Image:
    gray = image.convert("L")
    mask = gray.point(lambda value: 255 if value >= 170 else 0)
    bbox = mask.getbbox()
    if not bbox:
        return image
    x1, y1, x2, y2 = bbox
    if (x2 - x1) < image.width * 0.2 or (y2 - y1) < image.height * 0.15:
        return image
    pad_x = int((x2 - x1) * 0.05)
    pad_y = int((y2 - y1) * 0.07)
    return image.crop(
        (
            max(0, x1 - pad_x),
            max(0, y1 - pad_y),
            min(image.width, x2 + pad_x),
            min(image.height, y2 + pad_y),
        )
    )


def _build_variants(image: Image.Image) -> list[tuple[str, Image.Image]]:
    base = ImageOps.exif_transpose(image)
    scale = max(1.0, 2200 / max(base.size))
    if scale > 1.0:
        base = base.resize(
            (int(base.width * scale), int(base.height * scale)),
            Image.Resampling.LANCZOS,
        )
    cropped = _crop_label_region(base)
    variants: list[tuple[str, Image.Image]] = []
    for name, source in [("base", base), ("cropped", cropped)]:
        gray = source.convert("L")
        sharp = ImageEnhance.Sharpness(gray).enhance(2.0)
        contrast = ImageEnhance.Contrast(sharp).enhance(2.5).filter(ImageFilter.SHARPEN)
        auto = ImageOps.autocontrast(gray, cutoff=1)
        thr_130 = contrast.point(lambda value: 255 if value > 130 else 0)
        thr_150 = contrast.point(lambda value: 255 if value > 150 else 0)
        variants.extend(
            [
                (f"{name}-source", source),
                (f"{name}-contrast", contrast),
                (f"{name}-auto", auto),
                (f"{name}-thr130", thr_130),
                (f"{name}-thr150", thr_150),
            ]
        )
    return variants[:MAX_VARIANTS]


def _ensure_tesseract_ready() -> None:
    global _TESSERACT_READY
    if _TESSERACT_READY:
        return
    with _TESSERACT_LOCK:
        if _TESSERACT_READY:
            return
        import pytesseract

        pytesseract.get_tesseract_version()
        _TESSERACT_READY = True


def _run_tesseract_candidates(
    variants: list[tuple[str, Image.Image]],
    deadline: float | None = None,
) -> tuple[Optional[OCRCandidate], int, bool]:
    import pytesseract

    started = time.perf_counter()
    best: Optional[OCRCandidate] = None
    partial_timeout = False
    for variant_name, image in variants:
        for config in TESSERACT_CONFIGS:
            if deadline is not None and time.perf_counter() >= deadline:
                partial_timeout = True
                break
            try:
                text = pytesseract.image_to_string(image, config=config).strip()
            except Exception as exc:
                logger.debug("Tesseract failed for %s/%s: %s", variant_name, config, exc)
                continue
            score = _score_text(text)
            if best is None or score > best.score:
                best = OCRCandidate(text=text, score=score, variant=variant_name, config=config)
        if partial_timeout:
            break
    duration_ms = int((time.perf_counter() - started) * 1000)
    return best, duration_ms, partial_timeout


def _make_missing(candidates: Optional[list[str]] = None) -> ParsedField:
    return ParsedField(value=None, confidence=0.0, source_text="", candidates=candidates or [])


def _line_contains(line: str, keywords: list[str]) -> bool:
    tokenized = _normalize_token(line)
    return any(keyword in tokenized for keyword in keywords)


def _extract_material(lines: list[str]) -> ParsedField:
    candidates: list[str] = []
    source = ""
    for line in lines:
        for material, pattern in MATERIAL_PATTERNS:
            if pattern.search(line):
                source = source or line
                if material not in candidates:
                    candidates.append(material)
    if candidates:
        return ParsedField(candidates[0], 0.93, source, candidates[:5])
    return _make_missing(COMMON_MATERIALS[:5])


def _extract_brand(lines: list[str]) -> ParsedField:
    candidates: list[str] = []
    for line in lines[:8]:
        for brand, pattern, confidence in BRAND_PATTERNS:
            if pattern.search(line):
                if brand not in candidates:
                    candidates.append(brand)
                if confidence >= 0.92:
                    return ParsedField(brand, confidence, line, candidates[:5])
    if candidates:
        return ParsedField(candidates[0], 0.88, lines[0], candidates[:5])
    for line in lines[:4]:
        if re.search(r"\d", line):
            continue
        clean = re.sub(r"[^A-Za-z ]", "", line).strip()
        if len(clean) >= 4 and clean.isupper() and len(clean.split()) <= 3:
            title = clean.title()
            return ParsedField(title, 0.58, line, [title])
    return _make_missing(COMMON_BRANDS[:5])


def _extract_color(lines: list[str]) -> ParsedField:
    candidates: list[tuple[str, float, str]] = []
    for line in lines:
        normalized_line = _normalize_token(line)
        match = re.search(
            r"(?:color|farbe)\s*[:\-]?\s*([A-Za-z ]{2,24})",
            _normalize_text(line),
            re.IGNORECASE,
        )
        if match:
            candidates.append((match.group(1).strip(), 0.92, line))
        if "wood" in normalized_line or "burdy" in normalized_line or "burly" in normalized_line:
            candidates.append(("brown", 0.72, line))
        for name in COLOR_HEX_MAP:
            if re.search(rf"\b{re.escape(name)}\b", line, re.IGNORECASE):
                candidates.append((name, 0.70, line))

    best_value = None
    best_conf = 0.0
    best_source = ""
    best_candidates: list[str] = []
    for token, confidence, source in candidates:
        normalized = COLOR_ALIASES.get(_normalize_token(token), _normalize_token(token))
        if normalized in COLOR_HEX_MAP and confidence > best_conf:
            best_value = normalized
            best_conf = confidence
            best_source = source
        for canonical in COLOR_HEX_MAP:
            ratio = SequenceMatcher(None, normalized, canonical).ratio()
            adjusted_conf = 0.6 + (ratio - 0.86)
            if ratio >= 0.86 and adjusted_conf > best_conf:
                best_value = canonical
                best_conf = adjusted_conf
                best_source = source
        title = normalized.title() if normalized else ""
        if title and title not in best_candidates:
            best_candidates.append(title)

    if not best_value:
        return _make_missing(COMMON_COLORS[:5])
    return ParsedField(
        {"color_name": best_value.title(), "color_hex": COLOR_HEX_MAP[best_value]},
        min(best_conf, 0.95),
        best_source,
        best_candidates[:5] or [best_value.title()],
    )


def _extract_diameter(lines: list[str]) -> ParsedField:
    for line in lines:
        if not re.search(r"diam|mm|直径", line, re.IGNORECASE):
            continue
        match = re.search(
            r"([1-3](?:[.,]\d{1,2}))\s*(?:±|\+/-)?\s*\d*(?:[.,]\d+)?\s*mm",
            line,
            re.IGNORECASE,
        )
        if match:
            value = float(match.group(1).replace(",", "."))
            if 1.0 <= value <= 3.5:
                return ParsedField(value, 0.90, line, [str(value)])

    joined = " ".join(lines)
    match = re.search(r"\b([1-3](?:[.,]\d{1,2}))\s*mm\b", joined, re.IGNORECASE)
    if match:
        value = float(match.group(1).replace(",", "."))
        if 1.0 <= value <= 3.5:
            return ParsedField(value, 0.70, joined[:140], [str(value)])
    return _make_missing(["1.75"])


def _extract_weight(lines: list[str]) -> ParsedField:
    for line in lines:
        if not re.search(r"net|weight|n\.w\.|nw|重量", line, re.IGNORECASE):
            continue
        match = re.search(r"(\d+(?:[.,]\d+)?)\s*(kg|g)\b", line, re.IGNORECASE)
        if match:
            value = float(match.group(1).replace(",", "."))
            grams = int(round(value * 1000)) if match.group(2).lower() == "kg" else int(round(value))
            if 100 <= grams <= 5000:
                return ParsedField(grams, 0.92, line, [f"{grams}g"])

    joined = " ".join(lines)
    fallback = re.search(r"\b(\d+(?:[.,]\d+)?)\s*(kg|g)\b", joined, re.IGNORECASE)
    if fallback:
        value = float(fallback.group(1).replace(",", "."))
        grams = int(round(value * 1000)) if fallback.group(2).lower() == "kg" else int(round(value))
        if 100 <= grams <= 5000:
            return ParsedField(grams, 0.72, joined[:140], [f"{grams}g"])
    return _make_missing(["1000g"])


def _extract_temp_range(
    lines: list[str],
    keywords: list[str],
    bounds: tuple[int, int],
) -> ParsedField:
    low_bound, high_bound = bounds
    pattern = re.compile(
        r"(\d{2,3})\s*(?:°?\s*C)?\s*(?:-|~|to)\s*(\d{2,3})\s*(?:°?\s*C)?",
        re.IGNORECASE,
    )
    fallback: Optional[ParsedField] = None
    for line in lines:
        match = pattern.search(line)
        if not match:
            continue
        low, high = int(match.group(1)), int(match.group(2))
        if low > high:
            low, high = high, low
        if low < low_bound or high > high_bound:
            reject = ParsedField(
                {"min": low, "max": high},
                0.0,
                line,
                [f"{low}-{high}"],
                True,
            )
            fallback = fallback or reject
            continue
        confidence = 0.90 if _line_contains(line, keywords) else 0.62
        parsed = ParsedField({"min": low, "max": high}, confidence, line, [f"{low}-{high}"])
        if _line_contains(line, keywords):
            return parsed
        fallback = fallback or parsed
    return fallback or _make_missing()


def _status_for(field: ParsedField) -> str:
    if field.value is None:
        return "missing"
    if field.rejected:
        return "rejected"
    if field.confidence >= ACCEPTED_CONFIDENCE:
        return "accepted"
    if field.confidence >= LOW_CONFIDENCE:
        return "low_confidence"
    return "rejected"


def _accepted_value(field: ParsedField) -> Any:
    return field.value if _status_for(field) == "accepted" else None


def _suggestions_for_field(field: ParsedField, fallback: list[str]) -> list[str]:
    values: list[str] = []
    for candidate in field.candidates + fallback:
        normalized = str(candidate).strip()
        if normalized and normalized not in values:
            values.append(normalized)
    return values[:5]


def parse_label_text(text: str) -> dict[str, Any]:
    """Parse OCR text and return normalized spool fields and review metadata.

    Args:
    -----
        text (str):
            OCR raw output text.

    Returns:
    --------
        dict[str, Any]:
            Parsed result fields, per-field review metadata, warnings, and suggestions.
    """
    lines = [line.strip() for line in _normalize_text(text).splitlines() if line.strip()]
    brand = _extract_brand(lines)
    material = _extract_material(lines)
    color = _extract_color(lines)
    diameter = _extract_diameter(lines)
    weight = _extract_weight(lines)
    nozzle = _extract_temp_range(lines, ["print", "printing", "nozzle", "extruder"], (150, 350))
    bed = _extract_temp_range(lines, ["bed", "plate"], (20, 150))

    color_acc = _accepted_value(color)
    nozzle_acc = _accepted_value(nozzle)
    bed_acc = _accepted_value(bed)

    result = {
        "brand": _accepted_value(brand),
        "material": _accepted_value(material),
        "color_name": color_acc.get("color_name") if isinstance(color_acc, dict) else None,
        "color_hex": color_acc.get("color_hex") if isinstance(color_acc, dict) else None,
        "diameter_mm": _accepted_value(diameter),
        "weight_g": _accepted_value(weight),
        "nozzle_min": nozzle_acc.get("min") if isinstance(nozzle_acc, dict) else None,
        "nozzle_max": nozzle_acc.get("max") if isinstance(nozzle_acc, dict) else None,
        "bed_min": bed_acc.get("min") if isinstance(bed_acc, dict) else None,
        "bed_max": bed_acc.get("max") if isinstance(bed_acc, dict) else None,
    }

    source_map = {
        "brand": brand,
        "material": material,
        "color_name": color,
        "color_hex": color,
        "diameter_mm": diameter,
        "weight_g": weight,
        "nozzle_min": nozzle,
        "nozzle_max": nozzle,
        "bed_min": bed,
        "bed_max": bed,
    }
    review = {}
    warnings = []
    for key, field in source_map.items():
        status = _status_for(field)
        review[key] = {
            "status": status,
            "confidence": round(field.confidence, 3),
            "source_text": field.source_text,
            "candidates": field.candidates,
            "accepted_value": result[key],
        }
        if status in {"missing", "rejected"}:
            warnings.append(f"{key} not recognized")
        elif status == "low_confidence":
            warnings.append(f"{key} low confidence")

    fallback_recommended = any(
        review[field]["status"] != "accepted"
        for field in ("material", "diameter_mm", "weight_g")
    )
    suggestions = {
        "brand": _suggestions_for_field(brand, COMMON_BRANDS),
        "material": _suggestions_for_field(material, COMMON_MATERIALS),
        "color": _suggestions_for_field(color, COMMON_COLORS),
    }

    return {
        "result": result,
        "review": review,
        "warnings": warnings,
        "fallback_recommended": fallback_recommended,
        "suggestions": suggestions,
    }


def _run_tesseract_scan(
    image_bytes: bytes,
    *,
    timeout_seconds: float = 60,
    debug: bool = False,
) -> dict[str, Any]:
    """Run the local Tesseract OCR pipeline and return API payload.

    Args:
    -----
        image_bytes (bytes):
            Uploaded image content.
        timeout_seconds (float):
            Hard budget for OCR stage execution.
        debug (bool):
            Include debug metadata when enabled.

    Returns:
    --------
        dict[str, Any]:
            API response payload for OCR scan.
    """
    started = time.perf_counter()
    preprocess_started = time.perf_counter()
    try:
        image = _open_image_from_bytes(image_bytes)
        variants = _build_variants(image)
        preprocess_ms = int((time.perf_counter() - preprocess_started) * 1000)

        _ensure_tesseract_ready()
        deadline = time.perf_counter() + max(1.0, timeout_seconds)
        best, ocr_ms, partial_timeout = _run_tesseract_candidates(variants, deadline=deadline)

        parse_started = time.perf_counter()
        if best is None:
            parsed = {
                "result": {
                    "brand": None,
                    "material": None,
                    "color_name": None,
                    "color_hex": None,
                    "diameter_mm": None,
                    "weight_g": None,
                    "nozzle_min": None,
                    "nozzle_max": None,
                    "bed_min": None,
                    "bed_max": None,
                },
                "review": {
                    key: {
                        "status": "missing",
                        "confidence": 0.0,
                        "source_text": "",
                        "candidates": [],
                        "accepted_value": None,
                    }
                    for key in [
                        "brand",
                        "material",
                        "color_name",
                        "color_hex",
                        "diameter_mm",
                        "weight_g",
                        "nozzle_min",
                        "nozzle_max",
                        "bed_min",
                        "bed_max",
                    ]
                },
                "warnings": ["ocr extraction failed: no_ocr_result"],
                "fallback_recommended": True,
                "suggestions": {
                    "brand": COMMON_BRANDS[:5],
                    "material": COMMON_MATERIALS[:5],
                    "color": COMMON_COLORS[:5],
                },
            }
            selected_variant = None
            selected_config = None
            raw_text = ""
        else:
            parsed = parse_label_text(best.text)
            selected_variant = best.variant
            selected_config = best.config
            raw_text = best.text
        parse_ms = int((time.perf_counter() - parse_started) * 1000)
        total_ms = int((time.perf_counter() - started) * 1000)
        warnings = parsed["warnings"][:]
        if partial_timeout:
            warnings.append("partial timeout: OCR budget reached")

        payload = {
            "engine": "tesseract",
            "duration_ms": total_ms,
            "raw_text": raw_text,
            "warnings": warnings,
            "result": parsed["result"],
            "review": parsed["review"],
            "fallback_recommended": parsed["fallback_recommended"],
            "suggestions": parsed["suggestions"],
            "timing": {
                "total_ms": total_ms,
                "partial_timeout": partial_timeout,
                "stages": {
                    "preprocess_ms": preprocess_ms,
                    "ocr_ms": ocr_ms,
                    "parse_ms": parse_ms,
                    "variants": len(variants),
                    "selected_variant": selected_variant,
                    "selected_config": selected_config,
                },
            },
        }
        if debug:
            payload["debug"] = {"timeout_seconds": timeout_seconds}
        return payload
    except Exception as exc:
        total_ms = int((time.perf_counter() - started) * 1000)
        logger.exception("OCR scan failed: %s", exc)
        return {
            "engine": "tesseract",
            "duration_ms": total_ms,
            "raw_text": "",
            "warnings": [f"ocr extraction failed: {exc}"],
            "result": {
                "brand": None,
                "material": None,
                "color_name": None,
                "color_hex": None,
                "diameter_mm": None,
                "weight_g": None,
                "nozzle_min": None,
                "nozzle_max": None,
                "bed_min": None,
                "bed_max": None,
            },
            "review": {
                key: {
                    "status": "missing",
                    "confidence": 0.0,
                    "source_text": "",
                    "candidates": [],
                    "accepted_value": None,
                }
                for key in [
                    "brand",
                    "material",
                    "color_name",
                    "color_hex",
                    "diameter_mm",
                    "weight_g",
                    "nozzle_min",
                    "nozzle_max",
                    "bed_min",
                    "bed_max",
                ]
            },
            "fallback_recommended": True,
            "suggestions": {
                "brand": COMMON_BRANDS[:5],
                "material": COMMON_MATERIALS[:5],
                "color": COMMON_COLORS[:5],
            },
            "timing": {
                "total_ms": total_ms,
                "partial_timeout": False,
                "stages": {
                    "preprocess_ms": 0,
                    "ocr_ms": 0,
                    "parse_ms": 0,
                    "variants": 0,
                    "selected_variant": None,
                    "selected_config": None,
                },
            },
        }


def _required_fields_accepted(payload: dict[str, Any]) -> bool:
    """Check if required spool fields are confidently accepted.

    Args:
    -----
        payload (dict[str, Any]):
            OCR response payload.

    Returns:
    --------
        bool:
            True when required fields are accepted.
    """
    review = payload.get("review", {})
    required = ("material", "diameter_mm", "weight_g")
    for key in required:
        if review.get(key, {}).get("status") != "accepted":
            return False
    return True


def _fallback_reason(payload: dict[str, Any]) -> str | None:
    """Derive fallback reason from review status.

    Args:
    -----
        payload (dict[str, Any]):
            OCR response payload.

    Returns:
    --------
        str | None:
            Normalized reason or None.
    """
    review = payload.get("review", {})
    required = ("material", "diameter_mm", "weight_g")
    if any(review.get(key, {}).get("status") == "low_confidence" for key in required):
        return "low_confidence"
    if any(review.get(key, {}).get("status") in {"missing", "rejected"} for key in required):
        return "missing_required_fields"
    return None


def _payload_score(payload: dict[str, Any]) -> tuple[int, float]:
    """Score payload quality to choose the better provider output.

    Args:
    -----
        payload (dict[str, Any]):
            OCR response payload.

    Returns:
    --------
        tuple[int, float]:
            Accepted field count and sum of confidences.
    """
    review = payload.get("review", {})
    accepted = 0
    confidence_sum = 0.0
    for entry in review.values():
        if entry.get("status") == "accepted":
            accepted += 1
        confidence_sum += float(entry.get("confidence") or 0.0)
    return accepted, confidence_sum


def _normalize_provider_name(provider: str) -> str:
    """Normalize provider value.

    Args:
    -----
        provider (str):
            Raw provider name.

    Returns:
    --------
        str:
            Normalized provider name.
    """
    value = (provider or "").strip().lower()
    return value if value in {"openai", "claude"} else ""


def _provider_available(provider: str) -> bool:
    """Check if provider can be called with configured credentials.

    Args:
    -----
        provider (str):
            Provider name.

    Returns:
    --------
        bool:
            True if credentials are available.
    """
    if provider == "openai":
        return bool(OPENAI_API_KEY)
    if provider == "claude":
        return bool(ANTHROPIC_API_KEY)
    return False


def _detect_media_type(image_bytes: bytes) -> str:
    """Guess media type from image bytes.

    Args:
    -----
        image_bytes (bytes):
            Raw image bytes.

    Returns:
    --------
        str:
            Media type string.
    """
    if image_bytes.startswith(b"\xff\xd8"):
        return "image/jpeg"
    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
        return "image/webp"
    if image_bytes[4:12] == b"ftypheic" or image_bytes[4:12] == b"ftypheif":
        return "image/heic"
    return "image/jpeg"


def _extract_json_block(text: str) -> dict[str, Any] | None:
    """Extract first JSON object from provider text output.

    Args:
    -----
        text (str):
            Provider text output.

    Returns:
    --------
        dict[str, Any] | None:
            Parsed JSON object or None.
    """
    if not text:
        return None
    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start >= 0 and end > start:
        try:
            parsed = json.loads(stripped[start : end + 1])
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            return None
    return None


def _safe_float(value: Any) -> float | None:
    """Convert arbitrary value to float if possible.

    Args:
    -----
        value (Any):
            Input value.

    Returns:
    --------
        float | None:
            Parsed float or None.
    """
    if value is None:
        return None
    try:
        if isinstance(value, str):
            value = value.strip().replace(",", ".")
        parsed = float(value)
        return parsed if parsed == parsed else None
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> int | None:
    """Convert arbitrary value to int if possible.

    Args:
    -----
        value (Any):
            Input value.

    Returns:
    --------
        int | None:
            Parsed int or None.
    """
    parsed = _safe_float(value)
    if parsed is None:
        return None
    return int(round(parsed))


def _normalize_cloud_result(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize cloud OCR payload to local response contract.

    Args:
    -----
        payload (dict[str, Any]):
            Raw provider JSON fields.

    Returns:
    --------
        dict[str, Any]:
            Normalized OCR payload shape.
    """
    confidence_map = payload.get("confidence", {}) if isinstance(payload.get("confidence"), dict) else {}
    raw_brand = payload.get("brand")
    raw_material = payload.get("material")
    raw_color = payload.get("color_name")
    raw_color_hex = payload.get("color_hex")
    raw_diameter = _safe_float(payload.get("diameter_mm"))
    raw_weight = _safe_int(payload.get("weight_g"))
    raw_nozzle_min = _safe_int(payload.get("nozzle_min"))
    raw_nozzle_max = _safe_int(payload.get("nozzle_max"))
    raw_bed_min = _safe_int(payload.get("bed_min"))
    raw_bed_max = _safe_int(payload.get("bed_max"))

    if isinstance(raw_color, str):
        color_key = _normalize_token(raw_color)
        mapped = COLOR_ALIASES.get(color_key, color_key)
        if mapped in COLOR_HEX_MAP and not raw_color_hex:
            raw_color_hex = COLOR_HEX_MAP[mapped]
        if mapped in COLOR_HEX_MAP:
            raw_color = mapped.title()
    if isinstance(raw_color_hex, str):
        raw_color_hex = raw_color_hex.strip().upper()
        if raw_color_hex and not raw_color_hex.startswith("#"):
            raw_color_hex = f"#{raw_color_hex}"

    result = {
        "brand": raw_brand if isinstance(raw_brand, str) and raw_brand.strip() else None,
        "material": raw_material if isinstance(raw_material, str) and raw_material.strip() else None,
        "color_name": raw_color if isinstance(raw_color, str) and raw_color.strip() else None,
        "color_hex": raw_color_hex if isinstance(raw_color_hex, str) and raw_color_hex.strip() else None,
        "diameter_mm": raw_diameter if raw_diameter and 1.0 <= raw_diameter <= 3.5 else None,
        "weight_g": raw_weight if raw_weight and 100 <= raw_weight <= 5000 else None,
        "nozzle_min": raw_nozzle_min if raw_nozzle_min and 120 <= raw_nozzle_min <= 360 else None,
        "nozzle_max": raw_nozzle_max if raw_nozzle_max and 120 <= raw_nozzle_max <= 360 else None,
        "bed_min": raw_bed_min if raw_bed_min and 0 <= raw_bed_min <= 180 else None,
        "bed_max": raw_bed_max if raw_bed_max and 0 <= raw_bed_max <= 180 else None,
    }

    review: dict[str, dict[str, Any]] = {}
    warnings: list[str] = []
    for key in [
        "brand",
        "material",
        "color_name",
        "color_hex",
        "diameter_mm",
        "weight_g",
        "nozzle_min",
        "nozzle_max",
        "bed_min",
        "bed_max",
    ]:
        value = result.get(key)
        confidence = _safe_float(confidence_map.get(key))
        if confidence is None:
            confidence = 0.90 if value is not None else 0.0
        confidence = max(0.0, min(1.0, confidence))
        if value is None:
            status = "missing"
        elif confidence >= ACCEPTED_CONFIDENCE:
            status = "accepted"
        elif confidence >= LOW_CONFIDENCE:
            status = "low_confidence"
        else:
            status = "rejected"
        review[key] = {
            "status": status,
            "confidence": round(confidence, 3),
            "source_text": "cloud-vision",
            "candidates": [str(value)] if value is not None else [],
            "accepted_value": value if status == "accepted" else None,
        }
        if status in {"missing", "rejected"}:
            warnings.append(f"{key} not recognized")
        elif status == "low_confidence":
            warnings.append(f"{key} low confidence")

    fallback_recommended = any(
        review[field]["status"] != "accepted"
        for field in ("material", "diameter_mm", "weight_g")
    )
    suggestions = {
        "brand": [value for value in [result.get("brand")] + COMMON_BRANDS if value][:5],
        "material": [value for value in [result.get("material")] + COMMON_MATERIALS if value][:5],
        "color": [value for value in [result.get("color_name")] + COMMON_COLORS if value][:5],
    }
    return {
        "result": result,
        "review": review,
        "warnings": warnings,
        "fallback_recommended": fallback_recommended,
        "suggestions": suggestions,
    }


def _build_cloud_prompt() -> str:
    """Build extraction prompt for cloud providers.

    Returns:
    --------
        str:
            Prompt text with strict JSON output contract.
    """
    return (
        "Extract 3D filament label fields from the image. "
        "Return ONLY valid JSON with keys: "
        "brand, material, color_name, color_hex, diameter_mm, weight_g, "
        "nozzle_min, nozzle_max, bed_min, bed_max, confidence. "
        "confidence must be an object with same field keys mapped to 0..1. "
        "Use null when unknown. "
        "Normalize material to values like PLA, PLA+, PETG, ABS, ASA, TPU, PETG-CF. "
        "Normalize weight_g as grams, diameter_mm as float, temperatures as Celsius integers."
    )


def _call_openai_provider(
    image_bytes: bytes,
    *,
    timeout_seconds: float,
) -> dict[str, Any]:
    """Call OpenAI vision API and return normalized payload.

    Args:
    -----
        image_bytes (bytes):
            Raw image bytes.
        timeout_seconds (float):
            Request timeout.

    Returns:
    --------
        dict[str, Any]:
            Provider payload with parsed content.
    """
    media_type = _detect_media_type(image_bytes)
    image_b64 = base64.b64encode(image_bytes).decode("ascii")
    request_body = {
        "model": OPENAI_MODEL,
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": _build_cloud_prompt()},
                    {"type": "input_image", "image_url": f"data:{media_type};base64,{image_b64}"},
                ],
            }
        ],
    }
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=timeout_seconds) as client:
        response = client.post("https://api.openai.com/v1/responses", headers=headers, json=request_body)
        response.raise_for_status()
        payload = response.json()
    output_text = payload.get("output_text") or ""
    if not output_text:
        chunks = []
        for item in payload.get("output", []):
            for content in item.get("content", []):
                text = content.get("text")
                if text:
                    chunks.append(text)
        output_text = "\n".join(chunks)
    data = _extract_json_block(output_text)
    if data is None:
        parsed = parse_label_text(output_text)
        parsed["raw_text"] = output_text
        return parsed
    parsed = _normalize_cloud_result(data)
    parsed["raw_text"] = output_text
    return parsed


def _call_claude_provider(
    image_bytes: bytes,
    *,
    timeout_seconds: float,
) -> dict[str, Any]:
    """Call Claude vision API and return normalized payload.

    Args:
    -----
        image_bytes (bytes):
            Raw image bytes.
        timeout_seconds (float):
            Request timeout.

    Returns:
    --------
        dict[str, Any]:
            Provider payload with parsed content.
    """
    media_type = _detect_media_type(image_bytes)
    image_b64 = base64.b64encode(image_bytes).decode("ascii")
    request_body = {
        "model": ANTHROPIC_MODEL,
        "max_tokens": 900,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": _build_cloud_prompt()},
                    {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_b64}},
                ],
            }
        ],
    }
    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    with httpx.Client(timeout=timeout_seconds) as client:
        response = client.post("https://api.anthropic.com/v1/messages", headers=headers, json=request_body)
        response.raise_for_status()
        payload = response.json()
    output_text = "\n".join(
        item.get("text", "")
        for item in payload.get("content", [])
        if item.get("type") == "text"
    )
    data = _extract_json_block(output_text)
    if data is None:
        parsed = parse_label_text(output_text)
        parsed["raw_text"] = output_text
        return parsed
    parsed = _normalize_cloud_result(data)
    parsed["raw_text"] = output_text
    return parsed


def _call_cloud_provider(
    provider: str,
    image_bytes: bytes,
    *,
    timeout_seconds: float,
) -> dict[str, Any]:
    """Call selected cloud provider.

    Args:
    -----
        provider (str):
            Provider identifier.
        image_bytes (bytes):
            Raw image bytes.
        timeout_seconds (float):
            Request timeout.

    Returns:
    --------
        dict[str, Any]:
            Cloud extraction payload.

    Raises:
    -------
        ValueError:
            Raised when provider is unsupported.
    """
    if provider == "openai":
        return _call_openai_provider(image_bytes, timeout_seconds=timeout_seconds)
    if provider == "claude":
        return _call_claude_provider(image_bytes, timeout_seconds=timeout_seconds)
    raise ValueError(f"Unsupported provider: {provider}")


def _provider_order() -> list[str]:
    """Build cloud provider fallback order from environment.

    Returns:
    --------
        list[str]:
            Ordered provider list.
    """
    order: list[str] = []
    for provider in [_normalize_provider_name(OCR_PROVIDER_1), _normalize_provider_name(OCR_PROVIDER_2)]:
        if provider and provider not in order:
            order.append(provider)
    return order


def run_ocr_scan(
    image_bytes: bytes,
    *,
    timeout_seconds: float = 60,
    debug: bool = False,
) -> dict[str, Any]:
    """Run OCR with local-first and optional cloud fallback.

    Args:
    -----
        image_bytes (bytes):
            Uploaded image content.
        timeout_seconds (float):
            Hard budget for local OCR stage.
        debug (bool):
            Include debug metadata when enabled.

    Returns:
    --------
        dict[str, Any]:
            Final OCR payload including provider metadata.
    """
    started = time.perf_counter()
    local_timeout = timeout_seconds
    if OCR_ENABLE_CLOUD_FALLBACK:
        local_timeout = min(timeout_seconds, 9.0)
    total_budget = max(8.0, OCR_TOTAL_BUDGET_SECONDS)
    hard_deadline = started + total_budget
    base = _run_tesseract_scan(image_bytes, timeout_seconds=local_timeout, debug=debug)
    base.setdefault("provider_used", "tesseract")
    base.setdefault("provider_chain", ["tesseract"])
    base.setdefault("cloud_used", False)
    base.setdefault("fallback_reason", None)
    base.setdefault("timing", {})
    base["timing"].setdefault("stages", {})
    provider_chain = ["tesseract"]
    cloud_attempts: dict[str, int] = {}
    warnings = list(base.get("warnings", []))

    fallback_reason = _fallback_reason(base)
    chosen_payload = base
    chosen_provider = "tesseract"

    if OCR_ENABLE_CLOUD_FALLBACK and fallback_reason and time.perf_counter() < hard_deadline:
        for provider in _provider_order():
            remaining = hard_deadline - time.perf_counter()
            if remaining <= 0:
                warnings.append("partial timeout: overall OCR budget reached")
                break
            if not _provider_available(provider):
                warnings.append(f"{provider} provider skipped: missing api key")
                continue
            provider_chain.append(provider)
            attempt_started = time.perf_counter()
            try:
                candidate = _call_cloud_provider(
                    provider,
                    image_bytes,
                    timeout_seconds=max(1.8, min(OCR_CLOUD_TIMEOUT_SECONDS, 4.0, remaining)),
                )
            except Exception as exc:
                warnings.append(f"{provider} provider failed: {exc}")
                cloud_attempts[f"{provider}_ms"] = int((time.perf_counter() - attempt_started) * 1000)
                continue
            cloud_attempts[f"{provider}_ms"] = int((time.perf_counter() - attempt_started) * 1000)
            if _payload_score(candidate) > _payload_score(chosen_payload):
                chosen_payload = candidate
                chosen_provider = provider
            if _required_fields_accepted(candidate):
                chosen_payload = candidate
                chosen_provider = provider
                break

    total_ms = int((time.perf_counter() - started) * 1000)
    final_warnings = list(chosen_payload.get("warnings", [])) + warnings
    dedup_warnings = []
    for entry in final_warnings:
        if entry and entry not in dedup_warnings:
            dedup_warnings.append(entry)

    response = {
        "engine": "tesseract" if chosen_provider == "tesseract" else chosen_provider,
        "duration_ms": total_ms,
        "raw_text": chosen_payload.get("raw_text", ""),
        "warnings": dedup_warnings,
        "result": chosen_payload.get("result", {}),
        "review": chosen_payload.get("review", {}),
        "fallback_recommended": chosen_payload.get("fallback_recommended", True),
        "suggestions": chosen_payload.get("suggestions", {}),
        "timing": {
            **chosen_payload.get("timing", {}),
            "total_ms": total_ms,
            "stages": {
                **chosen_payload.get("timing", {}).get("stages", {}),
                **cloud_attempts,
            },
        },
        "provider_used": chosen_provider,
        "provider_chain": provider_chain,
        "fallback_reason": fallback_reason,
        "cloud_used": chosen_provider in {"openai", "claude"},
    }
    if debug:
        response["debug"] = {
            "local_timeout_seconds": timeout_seconds,
            "effective_local_timeout_seconds": local_timeout,
            "cloud_timeout_seconds": min(OCR_CLOUD_TIMEOUT_SECONDS, 4.0),
            "total_budget_seconds": total_budget,
            "provider_order": _provider_order(),
        }
    return response


def warmup_ocr_background() -> None:
    """Warm up Tesseract in a background thread."""

    if os.getenv("OCR_WARMUP", "1") != "1":
        return

    def _warmup() -> None:
        try:
            _ensure_tesseract_ready()
            logger.info("OCR warmup complete")
        except Exception as exc:
            logger.info("OCR warmup skipped: %s", exc)

    threading.Thread(target=_warmup, name="ocr-warmup", daemon=True).start()
