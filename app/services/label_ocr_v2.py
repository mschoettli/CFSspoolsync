"""OCR v2 pipeline for spool-label extraction."""

from __future__ import annotations

import io
import logging
import os
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
FAST_ACCEPT_SCORE = 55.0
FAST_VARIANT_LIMIT = 2
FAST_TESSERACT_VARIANT_LIMIT = 1

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

_PADDLE_ENGINE = None
_PADDLE_INIT_FAILED = False
_PADDLE_LOCK = threading.Lock()
_TESSERACT_ENGINE = None
_TESSERACT_LOCK = threading.Lock()


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


@dataclass
class OCRRunMeta:
    """Metadata for OCR runtime diagnostics."""

    partial_timeout: bool
    preprocess_ms: int
    fast_pass_ms: int
    deep_pass_ms: int
    paddle_ms: int
    tesseract_ms: int
    variants_fast: int
    variants_deep: int
    fast_phase_returned: bool
    timeout_reason: str


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
                if line and len(line) >= 2:
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
    for src, dst in {"Â°": "°", "º": "°", "–": "-", "—": "-", "−": "-"}.items():
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
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized.lower())
    return re.sub(r"\s+", " ", normalized).strip()


def _score_text(candidate: str) -> float:
    """Score OCR output quality."""
    stripped = candidate.strip()
    if not stripped:
        return 0.0
    normalized = _normalize_text(stripped)
    pats = [r"\b(?:PLA|PETG|ABS|ASA|TPU)\b", r"\b(?:COLOR|FARBE)\b", r"\b(?:TEMP|NOZZLE|BED)\b", r"\b(?:WEIGHT|N\.W\.)\b", r"\b(?:MM)\b"]
    hits = sum(bool(re.search(p, normalized, re.IGNORECASE)) for p in pats)
    return hits * 30 + min(sum(ch.isalnum() for ch in normalized), 500) * 0.08


def _deadline_exceeded(deadline: float | None) -> bool:
    """Check if an optional deadline is exceeded."""
    return deadline is not None and time.perf_counter() >= deadline


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


def _get_tesseract_engine() -> TesseractEngine:
    """Get cached Tesseract engine wrapper."""
    global _TESSERACT_ENGINE
    if _TESSERACT_ENGINE is not None:
        return _TESSERACT_ENGINE
    with _TESSERACT_LOCK:
        if _TESSERACT_ENGINE is None:
            _TESSERACT_ENGINE = TesseractEngine()
    return _TESSERACT_ENGINE


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
    return image.crop((max(0, x1 - pad_x), max(0, y1 - pad_y), min(image.width, x2 + pad_x), min(image.height, y2 + pad_y)))


def _build_variant_sets(image: Image.Image) -> tuple[list[Image.Image], list[Image.Image]]:
    """Create fast and deep OCR variants."""
    base = ImageOps.exif_transpose(image)
    scale = max(1.0, 2200 / max(base.size))
    if scale > 1.0:
        base = base.resize((int(base.width * scale), int(base.height * scale)), Image.Resampling.LANCZOS)
    cropped = _crop_label_region(base)
    fast: list[Image.Image] = []
    deep: list[Image.Image] = []
    for source in [base, cropped]:
        gray = source.convert("L")
        sharp = ImageEnhance.Sharpness(gray).enhance(2.0)
        contrast = ImageEnhance.Contrast(sharp).enhance(2.5).filter(ImageFilter.SHARPEN)
        auto = ImageOps.autocontrast(gray, cutoff=1)
        thr1 = contrast.point(lambda value: 255 if value > 130 else 0)
        thr2 = contrast.point(lambda value: 255 if value > 150 else 0)
        fast.extend([source, contrast])
        deep.extend([source, gray, auto, contrast, thr1, thr2])
    return fast, deep


def _best_result(engine: OCREngine, variants: list[Image.Image], *, deadline: float | None = None, max_variants: int | None = None) -> tuple[Optional[OCRResult], int, bool]:
    """Get best OCR result from one engine across variants."""
    started = time.perf_counter()
    best: Optional[OCRResult] = None
    partial_timeout = False
    seen = 0
    for variant in variants:
        if max_variants is not None and seen >= max_variants:
            break
        if _deadline_exceeded(deadline):
            partial_timeout = True
            break
        seen += 1
        try:
            texts = engine.extract_text(variant)
        except Exception as exc:
            logger.debug("OCR engine %s failed on variant: %s", engine.name, exc)
            continue
        for text in texts:
            score = _score_text(text)
            if best is None or score > best.score:
                best = OCRResult(text=text, engine=engine.name, score=score)
    return best, int((time.perf_counter() - started) * 1000), partial_timeout


def _extract_ocr_text(image_bytes: bytes, *, budget_seconds: float | None = None) -> tuple[Optional[OCRResult], OCRRunMeta]:
    """Run OCR with fast and deep passes under an optional time budget."""
    started = time.perf_counter()
    deadline = started + budget_seconds if budget_seconds else None
    preprocess_started = time.perf_counter()
    image = _open_image_from_bytes(image_bytes)
    fast_variants, deep_variants = _build_variant_sets(image)
    preprocess_ms = int((time.perf_counter() - preprocess_started) * 1000)

    partial_timeout = False
    timeout_reason = ""
    paddle_ms = 0
    tesseract_ms = 0
    best: Optional[OCRResult] = None
    fast_phase_returned = False

    fast_started = time.perf_counter()
    paddle_engine = _get_paddle_engine()
    if paddle_engine is not None:
        res, ms, pt = _best_result(paddle_engine, fast_variants, deadline=deadline, max_variants=FAST_VARIANT_LIMIT)
        paddle_ms += ms
        partial_timeout = partial_timeout or pt
        best = res if res is not None else best
    if best is None or best.score < FAST_ACCEPT_SCORE:
        res, ms, pt = _best_result(_get_tesseract_engine(), fast_variants, deadline=deadline, max_variants=FAST_TESSERACT_VARIANT_LIMIT)
        tesseract_ms += ms
        partial_timeout = partial_timeout or pt
        if res is not None and (best is None or res.score > best.score):
            best = res
    fast_pass_ms = int((time.perf_counter() - fast_started) * 1000)

    if best is not None and best.score >= FAST_ACCEPT_SCORE:
        fast_phase_returned = True
        return best, OCRRunMeta(partial_timeout, preprocess_ms, fast_pass_ms, 0, paddle_ms, tesseract_ms, len(fast_variants), len(deep_variants), fast_phase_returned, timeout_reason)

    if _deadline_exceeded(deadline):
        partial_timeout = True
        timeout_reason = "timeout_after_fast_pass"
        return best, OCRRunMeta(partial_timeout, preprocess_ms, fast_pass_ms, 0, paddle_ms, tesseract_ms, len(fast_variants), len(deep_variants), False, timeout_reason)

    deep_started = time.perf_counter()
    if paddle_engine is not None:
        res, ms, pt = _best_result(paddle_engine, deep_variants, deadline=deadline)
        paddle_ms += ms
        partial_timeout = partial_timeout or pt
        if res is not None and (best is None or res.score > best.score):
            best = res
    if not _deadline_exceeded(deadline):
        res, ms, pt = _best_result(_get_tesseract_engine(), deep_variants, deadline=deadline)
        tesseract_ms += ms
        partial_timeout = partial_timeout or pt
        if res is not None and (best is None or res.score > best.score):
            best = res
    else:
        partial_timeout = True
        timeout_reason = "timeout_before_deep_tesseract"
    deep_pass_ms = int((time.perf_counter() - deep_started) * 1000)
    if partial_timeout and not timeout_reason:
        timeout_reason = "partial_timeout_in_deep_pass"
    return best, OCRRunMeta(partial_timeout, preprocess_ms, fast_pass_ms, deep_pass_ms, paddle_ms, tesseract_ms, len(fast_variants), len(deep_variants), False, timeout_reason)


def _make_missing() -> ParsedField:
    """Create missing field marker."""
    return ParsedField(value=None, confidence=0.0, source_lines=[], candidates=[])


def _line_contains(line: str, keywords: list[str]) -> bool:
    """Check if normalized line contains any keyword."""
    lower = _normalize_token(line)
    return any(keyword in lower for keyword in keywords)


def _extract_material(lines: list[str]) -> ParsedField:
    candidates: list[str] = []
    for line in lines:
        for material, pattern in MATERIAL_PATTERNS:
            if pattern.search(line):
                if material not in candidates:
                    candidates.append(material)
    if candidates:
        return ParsedField(candidates[0], 0.93, [lines[0]], candidates[:3])
    return ParsedField(value=None, confidence=0.0, source_lines=[], candidates=COMMON_MATERIALS[:4])


def _extract_brand(lines: list[str]) -> ParsedField:
    found: list[str] = []
    for line in lines[:8]:
        for brand, pattern, confidence in BRAND_PATTERNS:
            if pattern.search(line):
                if brand not in found:
                    found.append(brand)
                if confidence >= 0.92:
                    return ParsedField(brand, confidence, [line], found[:3])
    if found:
        return ParsedField(found[0], 0.88, [lines[0]], found[:3])
    for line in lines[:4]:
        clean = re.sub(r"[^A-Za-z ]", "", line).strip()
        if re.search(r"\d", line):
            continue
        if len(clean) >= 4 and clean.isupper() and len(clean.split()) <= 3:
            title = clean.title()
            return ParsedField(title, 0.58, [line], [title])
    return ParsedField(value=None, confidence=0.0, source_lines=[], candidates=COMMON_BRANDS[:4])


def _extract_color(lines: list[str]) -> ParsedField:
    candidates: list[tuple[str, float, str]] = []
    for line in lines:
        normalized_line = _normalize_token(line)
        match = re.search(r"(?:color|farbe)\s*[:\-]?\s*([A-Za-z ]{2,24})", _normalize_text(line), re.IGNORECASE)
        if match:
            candidates.append((match.group(1).strip(), 0.92, line))
        if "wood" in normalized_line or "burdy" in normalized_line or "burly" in normalized_line:
            candidates.append(("brown", 0.72, line))
        for name in COLOR_HEX_MAP:
            if re.search(rf"\b{re.escape(name)}\b", line, re.IGNORECASE):
                candidates.append((name, 0.70, line))
    best_value = None
    best_conf = 0.0
    best_line = ""
    for token, conf, src in candidates:
        norm = COLOR_ALIASES.get(_normalize_token(token), _normalize_token(token))
        if norm in COLOR_HEX_MAP and conf > best_conf:
            best_value, best_conf, best_line = norm, conf, src
        for canonical in COLOR_HEX_MAP:
            score = SequenceMatcher(None, norm, canonical).ratio()
            if score >= 0.86 and (0.6 + (score - 0.86)) > best_conf:
                best_value, best_conf, best_line = canonical, 0.6 + (score - 0.86), src
    if not best_value:
        return ParsedField(value=None, confidence=0.0, source_lines=[], candidates=COMMON_COLORS[:5])
    return ParsedField({"color_name": best_value.title(), "color_hex": COLOR_HEX_MAP[best_value]}, min(best_conf, 0.95), [best_line] if best_line else [], [best_value.title()])


def _extract_diameter(lines: list[str]) -> ParsedField:
    for line in lines:
        if not re.search(r"diam|mm|直径", line, re.IGNORECASE):
            continue
        match = re.search(r"([1-3](?:[.,]\d{1,2}))\s*(?:±|\+/-)?\s*\d*(?:[.,]\d+)?\s*mm", line, re.IGNORECASE)
        if match:
            val = float(match.group(1).replace(",", "."))
            if 1.0 <= val <= 3.5:
                return ParsedField(val, 0.90, [line], [str(val)])
    for line in lines:
        match = re.search(r"\b([1-3](?:[.,]\d{1,2}))\s*mm\b", line, re.IGNORECASE)
        if match:
            val = float(match.group(1).replace(",", "."))
            if 1.0 <= val <= 3.5:
                return ParsedField(val, 0.78, [line], [str(val)])
    joined = " ".join(lines)
    match = re.search(r"\b([1-3](?:[.,]\d{1,2}))\s*mm\b", joined, re.IGNORECASE)
    if match:
        val = float(match.group(1).replace(",", "."))
        if 1.0 <= val <= 3.5:
            return ParsedField(val, 0.70, [joined[:140]], [str(val)])
    return _make_missing()


def _extract_weight(lines: list[str]) -> ParsedField:
    for line in lines:
        if not re.search(r"net|weight|n\.w\.|nw|重量", line, re.IGNORECASE):
            continue
        match = re.search(r"(\d+(?:[.,]\d+)?)\s*(kg|g)\b", line, re.IGNORECASE)
        if match:
            value = float(match.group(1).replace(",", "."))
            grams = int(round(value * 1000)) if match.group(2).lower() == "kg" else int(round(value))
            if 100 <= grams <= 5000:
                return ParsedField(grams, 0.92, [line], [f"{grams}g"])
    joined = " ".join(lines)
    fallback = re.search(r"\b(\d+(?:[.,]\d+)?)\s*(kg|g)\b", joined, re.IGNORECASE)
    if fallback:
        value = float(fallback.group(1).replace(",", "."))
        grams = int(round(value * 1000)) if fallback.group(2).lower() == "kg" else int(round(value))
        if 100 <= grams <= 5000:
            return ParsedField(grams, 0.72, [joined[:140]], [f"{grams}g"])
    return _make_missing()


def _extract_temp_range(lines: list[str], keywords: list[str], bounds: tuple[int, int]) -> ParsedField:
    low_bound, high_bound = bounds
    pattern = re.compile(r"(\d{2,3})\s*(?:°?\s*C)?\s*(?:-|~|to)\s*(\d{2,3})\s*(?:°?\s*C)?", re.IGNORECASE)
    fallback: Optional[ParsedField] = None
    for line in lines:
        match = pattern.search(line)
        if not match:
            continue
        low, high = int(match.group(1)), int(match.group(2))
        if low > high:
            low, high = high, low
        if low < low_bound or high > high_bound:
            reject = ParsedField({"min": low, "max": high}, 0.0, [line], [f"{low}-{high}"], True)
            fallback = fallback or reject
            continue
        conf = 0.90 if _line_contains(line, keywords) else 0.62
        cand = ParsedField({"min": low, "max": high}, conf, [line], [f"{low}-{high}"])
        if _line_contains(line, keywords):
            return cand
        fallback = fallback or cand
    return fallback or _make_missing()


def _field_status(field: ParsedField) -> str:
    if field.value is None:
        return "missing"
    if field.rejected:
        return "rejected_by_rule"
    if field.confidence >= ACCEPTED_CONFIDENCE:
        return "accepted"
    if field.confidence >= LOW_CONFIDENCE:
        return "low_confidence"
    return "rejected_by_rule"


def _accepted_value(field: ParsedField):
    return field.value if _field_status(field) == "accepted" else None


def _suggestions_for_field(parsed_field: ParsedField, fallback: list[str]) -> list[str]:
    """Build top suggestions for one field."""
    unique: list[str] = []
    for candidate in parsed_field.candidates + fallback:
        normalized = str(candidate).strip()
        if normalized and normalized not in unique:
            unique.append(normalized)
    return unique[:5]


def parse_ocr_text_v2(text: str) -> dict:
    """Parse OCR text into v2 structured fields and metadata."""
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
    fields = {
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

    raw_fields = {
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
    field_meta = {
        key: {
            "confidence": round(field.confidence, 3),
            "status": _field_status(field),
            "source_lines": field.source_lines,
            "accepted_value": fields[key],
            "candidates": field.candidates,
        }
        for key, field in raw_fields.items()
    }
    warnings = []
    for key, meta in field_meta.items():
        if meta["status"] in {"missing", "rejected_by_rule"}:
            warnings.append(f"{key} not recognized")
        elif meta["status"] == "low_confidence":
            warnings.append(f"{key} low confidence")
    fallback_recommended = any(
        field_meta[field]["status"] != "accepted"
        for field in ("material", "diameter_mm", "weight_g")
    )
    suggestions = {
        "brand": _suggestions_for_field(brand, COMMON_BRANDS),
        "material": _suggestions_for_field(material, COMMON_MATERIALS),
        "color_name": _suggestions_for_field(color, COMMON_COLORS),
    }
    return {
        "raw_text": text,
        "fields": fields,
        "field_meta": field_meta,
        "warnings": warnings,
        "fallback_recommended": fallback_recommended,
        "suggestions": suggestions,
    }


def _timing_payload(meta: OCRRunMeta, total_ms: int) -> dict[str, object]:
    return {
        "total_ms": total_ms,
        "partial_timeout": meta.partial_timeout,
        "stages": {
            "preprocess_ms": meta.preprocess_ms,
            "fast_pass_ms": meta.fast_pass_ms,
            "deep_pass_ms": meta.deep_pass_ms,
            "paddle_ms": meta.paddle_ms,
            "tesseract_ms": meta.tesseract_ms,
            "variants_fast": meta.variants_fast,
            "variants_deep": meta.variants_deep,
            "fast_phase_returned": meta.fast_phase_returned,
            "timeout_reason": meta.timeout_reason,
        },
    }


def _build_empty_response(reason: str, duration_ms: int, timing: dict[str, object]) -> dict:
    fields = {k: None for k in ["brand", "material", "color_name", "color_hex", "diameter_mm", "weight_g", "nozzle_min", "nozzle_max", "bed_min", "bed_max"]}
    meta = {k: {"confidence": 0.0, "status": "missing", "source_lines": [], "accepted_value": None, "candidates": []} for k in fields}
    return {
        "engine": "none",
        "duration_ms": duration_ms,
        "raw_text": "",
        "warnings": [f"ocr extraction failed: {reason}"],
        "fields": fields,
        "field_meta": meta,
        "fallback_recommended": True,
        "suggestions": {
            "brand": COMMON_BRANDS[:5],
            "material": COMMON_MATERIALS[:5],
            "color_name": COMMON_COLORS[:5],
        },
        "timing": timing,
    }


def run_ocr_v2(image_bytes: bytes, *, budget_seconds: float | None = None, debug: bool = False) -> dict:
    """Run complete OCR v2 pipeline and return API payload."""
    started = time.perf_counter()
    budget = budget_seconds if budget_seconds is not None else float(os.getenv("OCR_V2_INTERNAL_TIMEOUT_SECONDS", "110"))
    try:
        ocr, run_meta = _extract_ocr_text(image_bytes, budget_seconds=budget)
        duration_ms = int((time.perf_counter() - started) * 1000)
        timing = _timing_payload(run_meta, duration_ms)
        if ocr is None:
            payload = _build_empty_response("no_ocr_result", duration_ms, timing)
        else:
            parsed = parse_ocr_text_v2(ocr.text)
            warnings = parsed["warnings"][:]
            if run_meta.partial_timeout:
                warnings.append("partial timeout: deep analysis was truncated")
            payload = {
                "engine": ocr.engine,
                "duration_ms": duration_ms,
                "raw_text": parsed["raw_text"],
                "warnings": warnings,
                "fields": parsed["fields"],
                "field_meta": parsed["field_meta"],
                "fallback_recommended": parsed["fallback_recommended"],
                "suggestions": parsed["suggestions"],
                "timing": timing,
            }
        if debug:
            payload["debug"] = {"budget_seconds": budget}
        logger.info(
            "OCR v2 completed engine=%s total_ms=%s partial_timeout=%s",
            payload.get("engine"),
            duration_ms,
            payload.get("timing", {}).get("partial_timeout"),
        )
        return payload
    except Exception as exc:
        logger.exception("OCR v2 extraction failed: %s", exc)
        duration_ms = int((time.perf_counter() - started) * 1000)
        timing = {
            "total_ms": duration_ms,
            "partial_timeout": False,
            "stages": {
                "preprocess_ms": 0,
                "fast_pass_ms": 0,
                "deep_pass_ms": 0,
                "paddle_ms": 0,
                "tesseract_ms": 0,
                "variants_fast": 0,
                "variants_deep": 0,
                "fast_phase_returned": False,
                "timeout_reason": "exception",
            },
        }
        return _build_empty_response(str(exc), duration_ms, timing)


def warmup_ocr_v2_background() -> None:
    """Warm up OCR engines in a background thread."""
    if os.getenv("OCR_V2_WARMUP", "1") != "1":
        return

    def _warmup() -> None:
        try:
            _get_paddle_engine()
            _get_tesseract_engine()
            logger.info("OCR v2 warmup complete")
        except Exception as exc:
            logger.info("OCR v2 warmup skipped: %s", exc)

    threading.Thread(target=_warmup, name="ocr-v2-warmup", daemon=True).start()
