"""OCR v2 pipeline for spool-label extraction."""

from __future__ import annotations

import io
import logging
import re
import threading
import time
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Optional

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

logger = logging.getLogger(__name__)

ACCEPTED_CONFIDENCE = 0.80
LOW_CONFIDENCE = 0.55

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
    "weiB": "white",
    "weiß": "white",
    "schwarz": "black",
    "grau": "gray",
    "golden": "gold",
    "biack": "black",
    "burdy": "brown",
    "wood": "brown",
    "burdy wood": "brown",
}

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

_PADDLE_ENGINE = None
_PADDLE_INIT_FAILED = False
_PADDLE_LOCK = threading.Lock()


@dataclass
class OCRResult:
    """OCR output with source engine and score."""

    text: str
    engine: str
    score: float


@dataclass
class ParsedField:
    """Parsed field with confidence and source traces."""

    value: object
    confidence: float
    source_lines: list[str]
    candidates: list[str]
    rejected: bool = False


class OCREngine:
    """Base class for OCR engines."""

    name = "unknown"

    def extract_text(self, image: Image.Image) -> list[str]:
        """Extract text candidates for one image."""
        raise NotImplementedError


class PaddleOCREngine(OCREngine):
    """PaddleOCR backend."""

    name = "paddle"

    def __init__(self) -> None:
        """Initialize PaddleOCR engine."""
        from paddleocr import PaddleOCR

        self._ocr = PaddleOCR(use_angle_cls=True, lang="en", use_gpu=False, show_log=False)

    def extract_text(self, image: Image.Image) -> list[str]:
        """Extract OCR text with PaddleOCR."""
        import numpy as np

        result = self._ocr.ocr(np.array(image), cls=True)
        if not result:
            return []
        lines: list[str] = []
        for block in result:
            if not block:
                continue
            for line in block:
                if not line or len(line) < 2:
                    continue
                text = str(line[1][0]).strip()
                if text:
                    lines.append(text)
        return ["\n".join(lines)] if lines else []


class TesseractEngine(OCREngine):
    """Tesseract backend."""

    name = "tesseract"

    def extract_text(self, image: Image.Image) -> list[str]:
        """Extract OCR text with multiple Tesseract configs."""
        import pytesseract

        return [
            pytesseract.image_to_string(image, config="--oem 3 --psm 6 -l eng"),
            pytesseract.image_to_string(image, config="--oem 3 --psm 4 -l eng"),
            pytesseract.image_to_string(image, config="--oem 3 --psm 11 -l eng"),
            pytesseract.image_to_string(image, config="--oem 1 --psm 6 -l eng"),
        ]


def _normalize_text(text: str) -> str:
    """Normalize OCR text before parsing."""
    normalized = unicodedata.normalize("NFKC", text or "")
    replacements = {
        "Â°": "°",
        "º": "°",
        "–": "-",
        "—": "-",
        "−": "-",
    }
    for src, dst in replacements.items():
        normalized = normalized.replace(src, dst)
    normalized = re.sub(r"(?<=\d)[Oo](?=\d)", "0", normalized)
    normalized = re.sub(r"(?<=\d)[Il](?=\d)", "1", normalized)
    normalized = re.sub(r"[ \t]+", " ", normalized)
    return normalized.strip()


def _normalize_token(value: str) -> str:
    """Normalize token for fuzzy comparisons."""
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKD", value)
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = normalized.lower()
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _score_text(candidate: str) -> float:
    """Score OCR output quality."""
    stripped = candidate.strip()
    if not stripped:
        return 0.0
    normalized = _normalize_text(stripped)
    keywords = [
        r"\b(?:PLA|PETG|ABS|ASA|TPU)\b",
        r"\b(?:COLOR|FARBE)\b",
        r"\b(?:TEMP|NOZZLE|BED)\b",
        r"\b(?:WEIGHT|N\.W\.)\b",
        r"\b(?:MM)\b",
    ]
    keyword_hits = sum(bool(re.search(pattern, normalized, re.IGNORECASE)) for pattern in keywords)
    alnum_chars = sum(char.isalnum() for char in normalized)
    return keyword_hits * 30 + min(alnum_chars, 500) * 0.08


def _get_paddle_engine() -> Optional[PaddleOCREngine]:
    """Get cached PaddleOCR engine."""
    global _PADDLE_ENGINE, _PADDLE_INIT_FAILED
    if _PADDLE_ENGINE is not None:
        return _PADDLE_ENGINE
    if _PADDLE_INIT_FAILED:
        return None

    with _PADDLE_LOCK:
        if _PADDLE_ENGINE is not None:
            return _PADDLE_ENGINE
        if _PADDLE_INIT_FAILED:
            return None
        try:
            _PADDLE_ENGINE = PaddleOCREngine()
        except Exception as exc:
            _PADDLE_INIT_FAILED = True
            logger.info("PaddleOCR unavailable, fallback to Tesseract: %s", exc)
            return None
    return _PADDLE_ENGINE


def _open_image_from_bytes(image_bytes: bytes) -> Image.Image:
    """Open image bytes with optional HEIC support."""
    try:
        import pillow_heif

        pillow_heif.register_heif_opener()
    except Exception:
        pass
    return Image.open(io.BytesIO(image_bytes))


def _crop_label_region(image: Image.Image) -> Image.Image:
    """Crop likely bright label area."""
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
    left = max(0, x1 - pad_x)
    top = max(0, y1 - pad_y)
    right = min(image.width, x2 + pad_x)
    bottom = min(image.height, y2 + pad_y)
    return image.crop((left, top, right, bottom))


def _build_variants(image: Image.Image) -> list[Image.Image]:
    """Create OCR-friendly image variants."""
    base = ImageOps.exif_transpose(image)
    width, height = base.size
    scale = max(1.0, 2200 / max(width, height))
    if scale > 1.0:
        base = base.resize((int(width * scale), int(height * scale)), Image.Resampling.LANCZOS)

    cropped = _crop_label_region(base)
    variants: list[Image.Image] = []
    for source in [base, cropped]:
        gray = source.convert("L")
        sharp = ImageEnhance.Sharpness(gray).enhance(2.0)
        contrast = ImageEnhance.Contrast(sharp).enhance(2.5).filter(ImageFilter.SHARPEN)
        auto = ImageOps.autocontrast(gray, cutoff=1)
        threshold_1 = contrast.point(lambda value: 255 if value > 130 else 0)
        threshold_2 = contrast.point(lambda value: 255 if value > 150 else 0)
        variants.extend([source, gray, auto, contrast, threshold_1, threshold_2])
    return variants


def _best_result(engine: OCREngine, variants: list[Image.Image]) -> Optional[OCRResult]:
    """Get best OCR result from one engine across variants."""
    best: Optional[OCRResult] = None
    for variant in variants:
        try:
            texts = engine.extract_text(variant)
        except Exception as exc:
            logger.debug("OCR engine %s failed on variant: %s", engine.name, exc)
            continue
        for text in texts:
            score = _score_text(text)
            if best is None or score > best.score:
                best = OCRResult(text=text, engine=engine.name, score=score)
    return best


def _extract_ocr_text(image_bytes: bytes) -> OCRResult:
    """Run OCR with Paddle primary and Tesseract fallback."""
    image = _open_image_from_bytes(image_bytes)
    variants = _build_variants(image)

    paddle_engine = _get_paddle_engine()
    paddle_result: Optional[OCRResult] = None
    if paddle_engine is not None:
        paddle_result = _best_result(paddle_engine, variants)
    if paddle_result and paddle_result.score >= 35.0:
        return paddle_result

    tesseract_result = _best_result(TesseractEngine(), variants)
    if tesseract_result is not None:
        return tesseract_result
    if paddle_result is not None:
        return paddle_result
    raise RuntimeError("No OCR output from Paddle or Tesseract")


def _make_missing() -> ParsedField:
    """Create missing field marker."""
    return ParsedField(value=None, confidence=0.0, source_lines=[], candidates=[])


def _line_contains(line: str, keywords: list[str]) -> bool:
    """Check if normalized line contains any keyword."""
    lower = _normalize_token(line)
    return any(keyword in lower for keyword in keywords)


def _extract_material(lines: list[str]) -> ParsedField:
    """Extract material with OCR-tolerant patterns."""
    for line in lines:
        for material, pattern in MATERIAL_PATTERNS:
            if pattern.search(line):
                return ParsedField(
                    value=material,
                    confidence=0.93,
                    source_lines=[line],
                    candidates=[material],
                )
    return _make_missing()


def _extract_brand(lines: list[str]) -> ParsedField:
    """Extract brand from header/brand context."""
    for line in lines[:8]:
        for brand, pattern, confidence in BRAND_PATTERNS:
            if pattern.search(line):
                return ParsedField(
                    value=brand,
                    confidence=confidence,
                    source_lines=[line],
                    candidates=[brand],
                )
    # Header fallback: first short all-caps token line.
    for line in lines[:4]:
        cleaned = re.sub(r"[^A-Za-z ]", "", line).strip()
        if len(cleaned) < 4:
            continue
        if cleaned.isupper() and len(cleaned.split()) <= 3:
            return ParsedField(
                value=cleaned.title(),
                confidence=0.58,
                source_lines=[line],
                candidates=[cleaned.title()],
            )
    return _make_missing()


def _extract_color(lines: list[str]) -> ParsedField:
    """Extract color from color-specific context lines."""
    candidates: list[tuple[str, float, str]] = []
    for line in lines:
        normalized_line = _normalize_text(line)
        label_match = re.search(r"(?:color|farbe|颜[色色])\s*[:\-]?\s*([A-Za-z ]{2,24})", normalized_line, re.IGNORECASE)
        if label_match:
            token = label_match.group(1).strip()
            candidates.append((token, 0.92, line))

    for line in lines:
        for color_name in COLOR_HEX_MAP:
            if re.search(rf"\b{re.escape(color_name)}\b", line, re.IGNORECASE):
                candidates.append((color_name, 0.70, line))

    best_value = None
    best_conf = 0.0
    best_line = ""
    for token, confidence, source_line in candidates:
        normalized = _normalize_token(token)
        normalized = COLOR_ALIASES.get(normalized, normalized)
        if normalized in COLOR_HEX_MAP and confidence > best_conf:
            best_value = normalized
            best_conf = confidence
            best_line = source_line
            continue

        for canonical in COLOR_HEX_MAP:
            fuzzy_score = SequenceMatcher(None, normalized, canonical).ratio()
            if fuzzy_score >= 0.86 and (0.6 + (fuzzy_score - 0.86)) > best_conf:
                best_value = canonical
                best_conf = 0.6 + (fuzzy_score - 0.86)
                best_line = source_line

    if not best_value:
        return _make_missing()
    return ParsedField(
        value={"color_name": best_value.title(), "color_hex": COLOR_HEX_MAP[best_value]},
        confidence=min(best_conf, 0.95),
        source_lines=[best_line] if best_line else [],
        candidates=[best_value.title()],
    )


def _extract_diameter(lines: list[str]) -> ParsedField:
    """Extract filament diameter in mm."""
    for line in lines:
        if not re.search(r"diam|mm|直径", line, re.IGNORECASE):
            continue
        match = re.search(r"([1-3](?:[.,]\d{1,2}))\s*(?:±|\+/-)?\s*\d*(?:[.,]\d+)?\s*mm", line, re.IGNORECASE)
        if not match:
            continue
        diameter = float(match.group(1).replace(",", "."))
        if 1.0 <= diameter <= 3.5:
            return ParsedField(
                value=diameter,
                confidence=0.9,
                source_lines=[line],
                candidates=[str(diameter)],
            )
    # fallback for lines containing plain 1.75mm
    for line in lines:
        match = re.search(r"\b([1-3](?:[.,]\d{1,2}))\s*mm\b", line, re.IGNORECASE)
        if not match:
            continue
        diameter = float(match.group(1).replace(",", "."))
        if 1.0 <= diameter <= 3.5:
            return ParsedField(
                value=diameter,
                confidence=0.78,
                source_lines=[line],
                candidates=[str(diameter)],
            )
    return _make_missing()


def _extract_weight(lines: list[str]) -> ParsedField:
    """Extract net weight in grams."""
    for line in lines:
        if not re.search(r"net|weight|n\.w\.|nw|重量", line, re.IGNORECASE):
            continue
        match = re.search(r"(\d+(?:[.,]\d+)?)\s*(kg|g)\b", line, re.IGNORECASE)
        if not match:
            continue
        value = float(match.group(1).replace(",", "."))
        unit = match.group(2).lower()
        grams = int(round(value * 1000)) if unit == "kg" else int(round(value))
        if 100 <= grams <= 5000:
            return ParsedField(
                value=grams,
                confidence=0.92,
                source_lines=[line],
                candidates=[f"{grams}g"],
            )
    return _make_missing()


def _extract_temp_range(lines: list[str], keywords: list[str], bounds: tuple[int, int]) -> ParsedField:
    """Extract temperature range with keyword context."""
    lower_bound, upper_bound = bounds
    pattern = re.compile(
        r"(\d{2,3})\s*(?:°?\s*C)?\s*(?:-|~|to)\s*(\d{2,3})\s*(?:°?\s*C)?",
        re.IGNORECASE,
    )
    fallback_candidate: Optional[ParsedField] = None
    for line in lines:
        match = pattern.search(line)
        if not match:
            continue
        low = int(match.group(1))
        high = int(match.group(2))
        if low > high:
            low, high = high, low
        if low < lower_bound or high > upper_bound:
            rejected = ParsedField(
                value={"min": low, "max": high},
                confidence=0.0,
                source_lines=[line],
                candidates=[f"{low}-{high}"],
                rejected=True,
            )
            if fallback_candidate is None:
                fallback_candidate = rejected
            continue
        confidence = 0.9 if _line_contains(line, keywords) else 0.62
        candidate = ParsedField(
            value={"min": low, "max": high},
            confidence=confidence,
            source_lines=[line],
            candidates=[f"{low}-{high}"],
        )
        if _line_contains(line, keywords):
            return candidate
        if fallback_candidate is None:
            fallback_candidate = candidate
    return fallback_candidate if fallback_candidate is not None else _make_missing()


def _field_status(parsed_field: ParsedField) -> str:
    """Map parsed field confidence to API status."""
    if parsed_field.value is None:
        return "missing"
    if parsed_field.rejected:
        return "rejected_by_rule"
    if parsed_field.confidence >= ACCEPTED_CONFIDENCE:
        return "accepted"
    if parsed_field.confidence >= LOW_CONFIDENCE:
        return "low_confidence"
    return "rejected_by_rule"


def _accepted_value(parsed_field: ParsedField):
    """Return accepted value or null for low-confidence fields."""
    return parsed_field.value if _field_status(parsed_field) == "accepted" else None


def parse_ocr_text_v2(text: str) -> dict:
    """Parse OCR text into v2 structured fields and metadata."""
    normalized = _normalize_text(text)
    lines = [line.strip() for line in normalized.splitlines() if line.strip()]

    brand = _extract_brand(lines)
    material = _extract_material(lines)
    color = _extract_color(lines)
    diameter = _extract_diameter(lines)
    weight = _extract_weight(lines)
    nozzle = _extract_temp_range(lines, ["print", "printing", "nozzle", "extruder"], (150, 350))
    bed = _extract_temp_range(lines, ["bed", "plate"], (20, 150))

    fields = {
        "brand": _accepted_value(brand),
        "material": _accepted_value(material),
        "color_name": _accepted_value(color).get("color_name") if isinstance(_accepted_value(color), dict) else None,
        "color_hex": _accepted_value(color).get("color_hex") if isinstance(_accepted_value(color), dict) else None,
        "diameter_mm": _accepted_value(diameter),
        "weight_g": _accepted_value(weight),
        "nozzle_min": _accepted_value(nozzle).get("min") if isinstance(_accepted_value(nozzle), dict) else None,
        "nozzle_max": _accepted_value(nozzle).get("max") if isinstance(_accepted_value(nozzle), dict) else None,
        "bed_min": _accepted_value(bed).get("min") if isinstance(_accepted_value(bed), dict) else None,
        "bed_max": _accepted_value(bed).get("max") if isinstance(_accepted_value(bed), dict) else None,
    }

    field_meta = {
        "brand": {
            "confidence": round(brand.confidence, 3),
            "status": _field_status(brand),
            "source_lines": brand.source_lines,
            "accepted_value": fields["brand"],
            "candidates": brand.candidates,
        },
        "material": {
            "confidence": round(material.confidence, 3),
            "status": _field_status(material),
            "source_lines": material.source_lines,
            "accepted_value": fields["material"],
            "candidates": material.candidates,
        },
        "color_name": {
            "confidence": round(color.confidence, 3),
            "status": _field_status(color),
            "source_lines": color.source_lines,
            "accepted_value": fields["color_name"],
            "candidates": color.candidates,
        },
        "color_hex": {
            "confidence": round(color.confidence, 3),
            "status": _field_status(color),
            "source_lines": color.source_lines,
            "accepted_value": fields["color_hex"],
            "candidates": color.candidates,
        },
        "diameter_mm": {
            "confidence": round(diameter.confidence, 3),
            "status": _field_status(diameter),
            "source_lines": diameter.source_lines,
            "accepted_value": fields["diameter_mm"],
            "candidates": diameter.candidates,
        },
        "weight_g": {
            "confidence": round(weight.confidence, 3),
            "status": _field_status(weight),
            "source_lines": weight.source_lines,
            "accepted_value": fields["weight_g"],
            "candidates": weight.candidates,
        },
        "nozzle_min": {
            "confidence": round(nozzle.confidence, 3),
            "status": _field_status(nozzle),
            "source_lines": nozzle.source_lines,
            "accepted_value": fields["nozzle_min"],
            "candidates": nozzle.candidates,
        },
        "nozzle_max": {
            "confidence": round(nozzle.confidence, 3),
            "status": _field_status(nozzle),
            "source_lines": nozzle.source_lines,
            "accepted_value": fields["nozzle_max"],
            "candidates": nozzle.candidates,
        },
        "bed_min": {
            "confidence": round(bed.confidence, 3),
            "status": _field_status(bed),
            "source_lines": bed.source_lines,
            "accepted_value": fields["bed_min"],
            "candidates": bed.candidates,
        },
        "bed_max": {
            "confidence": round(bed.confidence, 3),
            "status": _field_status(bed),
            "source_lines": bed.source_lines,
            "accepted_value": fields["bed_max"],
            "candidates": bed.candidates,
        },
    }

    warnings: list[str] = []
    for field_name, meta in field_meta.items():
        if meta["status"] in {"missing", "rejected_by_rule"}:
            warnings.append(f"{field_name} not recognized")
        elif meta["status"] == "low_confidence":
            warnings.append(f"{field_name} low confidence")

    return {
        "raw_text": text,
        "fields": fields,
        "field_meta": field_meta,
        "warnings": warnings,
    }


def _build_empty_response(reason: str, duration_ms: int) -> dict:
    """Build a fallback OCR response when extraction fails.

    Args:
    -----
        reason (str):
            Failure reason for warnings.
        duration_ms (int):
            Processing duration in milliseconds.

    Returns:
    --------
        dict:
            OCR v2-compatible empty payload.
    """
    fields = {
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
    }
    field_meta = {
        key: {
            "confidence": 0.0,
            "status": "missing",
            "source_lines": [],
            "accepted_value": None,
            "candidates": [],
        }
        for key in fields
    }
    return {
        "engine": "none",
        "duration_ms": duration_ms,
        "raw_text": "",
        "warnings": [f"ocr extraction failed: {reason}"],
        "fields": fields,
        "field_meta": field_meta,
    }


def run_ocr_v2(image_bytes: bytes) -> dict:
    """Run complete OCR v2 pipeline and return API payload."""
    started = time.perf_counter()
    try:
        ocr = _extract_ocr_text(image_bytes)
        parsed = parse_ocr_text_v2(ocr.text)
        duration_ms = int((time.perf_counter() - started) * 1000)
        return {
            "engine": ocr.engine,
            "duration_ms": duration_ms,
            "raw_text": parsed["raw_text"],
            "warnings": parsed["warnings"],
            "fields": parsed["fields"],
            "field_meta": parsed["field_meta"],
        }
    except Exception as exc:
        logger.exception("OCR v2 extraction failed: %s", exc)
        duration_ms = int((time.perf_counter() - started) * 1000)
        return _build_empty_response(str(exc), duration_ms)
