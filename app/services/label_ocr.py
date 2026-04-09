"""OCR helpers for extracting spool data from label photos."""

import logging
import re
import threading
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Optional

logger = logging.getLogger(__name__)
BRAND_APPLY_THRESHOLD = 0.65
OCR_FALLBACK_MIN_SCORE = 35.0

MATERIAL_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("PETG-CF", re.compile(r"\bPETG\s*[-+ ]\s*CF\b", re.IGNORECASE)),
    ("PETG-GF", re.compile(r"\bPETG\s*[-+ ]\s*GF\b", re.IGNORECASE)),
    ("PLA+", re.compile(r"\bP[L1I][A4]\s*\+\b", re.IGNORECASE)),
    ("PETG", re.compile(r"\bPETG\b", re.IGNORECASE)),
    ("PLA", re.compile(r"\bP[L1I][A4]\b", re.IGNORECASE)),
    ("ABS", re.compile(r"\bABS\b", re.IGNORECASE)),
    ("ASA", re.compile(r"\bASA\b", re.IGNORECASE)),
    ("TPU", re.compile(r"\bTPU\b", re.IGNORECASE)),
    ("TPE", re.compile(r"\bTPE\b", re.IGNORECASE)),
    ("NYLON", re.compile(r"\bNYLON\b", re.IGNORECASE)),
    ("PA", re.compile(r"\bPA(?:6|12|66)?\b", re.IGNORECASE)),
    ("PC", re.compile(r"\bPC\b", re.IGNORECASE)),
    ("HIPS", re.compile(r"\bHIPS\b", re.IGNORECASE)),
    ("PVA", re.compile(r"\bPVA\b", re.IGNORECASE)),
    ("CPE", re.compile(r"\bCPE\b", re.IGNORECASE)),
    ("PP", re.compile(r"\bPP\b", re.IGNORECASE)),
    ("PEEK", re.compile(r"\bPEEK\b", re.IGNORECASE)),
    ("CF", re.compile(r"\bCF\b", re.IGNORECASE)),
    ("GF", re.compile(r"\bGF\b", re.IGNORECASE)),
]

COLOR_MAP = {
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
    "matte black": "black",
    "charcoal": "black",
    "forest green": "green",
    "emerald green": "emerald",
    "space gray": "gray",
    "cool grey": "grey",
    "weiß": "white",
    "weiss": "white",
    "schwarz": "black",
    "grau": "gray",
    "grun": "green",
    "grün": "green",
    "blau": "blue",
    "rot": "red",
    "natur": "natural",
    "naturlich": "natural",
    "natürlich": "natural",
    "klar": "transparent",
}

BRAND_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("Bambu Lab", re.compile(r"\bBAMBU\s*LAB\b", re.IGNORECASE)),
    ("Prusament", re.compile(r"\bPRUSAMENT\b", re.IGNORECASE)),
    ("Polymaker", re.compile(r"\bPOLYMAKER\b", re.IGNORECASE)),
    ("Overture", re.compile(r"\bOVERTURE\b", re.IGNORECASE)),
    ("Sunlu", re.compile(r"\bSUNLU\b", re.IGNORECASE)),
    ("eSUN", re.compile(r"\bE[\s\-]?SUN\b", re.IGNORECASE)),
    ("Anycubic", re.compile(r"\bANYCUBIC\b", re.IGNORECASE)),
    ("Creality", re.compile(r"\bCREALITY\b", re.IGNORECASE)),
    ("Creality", re.compile(r"\bENDER(?:\s*[- ]?PLA)?\b", re.IGNORECASE)),
    ("Geeetech", re.compile(r"\bGEE+\s*[\+\-]?\s*TECH\b", re.IGNORECASE)),
]

STATIC_BRAND_CANONICALS = [
    "Bambu Lab",
    "Prusament",
    "Polymaker",
    "Overture",
    "Sunlu",
    "eSUN",
    "Anycubic",
    "Creality",
    "Geeetech",
]

_PADDLE_ENGINE = None
_PADDLE_INIT_FAILED = False
_PADDLE_LOCK = threading.Lock()

DEFAULT_FIELDS = {
    "brand": "",
    "material": "",
    "color": "#888888",
    "color_name": "",
    "nozzle_min": 0,
    "nozzle_max": 0,
    "bed_min": 0,
    "bed_max": 0,
    "diameter": 1.75,
    "weight_g": None,
}


def _normalize_text(text: str) -> str:
    """Normalize OCR text for more robust parsing.

    Args:
    -----
        text (str):
            Raw OCR output.

    Returns:
    --------
        str:
            Normalized text with unified punctuation and symbols.
    """
    normalized = unicodedata.normalize("NFKC", text or "")
    replacements = {
        "Â°": "°",
        "º": "°",
        "â€“": "-",
        "â€”": "-",
        "–": "-",
        "—": "-",
        "−": "-",
        "~": "-",
    }
    for src, dst in replacements.items():
        normalized = normalized.replace(src, dst)

    # Fix common OCR substitution O <-> 0 when close to numeric context.
    normalized = re.sub(r"(?<=\d)[Oo](?=\d)", "0", normalized)
    normalized = re.sub(r"(?<=\b)[Oo](?=\d)", "0", normalized)
    normalized = re.sub(r"(?<=\d)[Oo](?=\b)", "0", normalized)
    normalized = re.sub(r"[ \t]+", " ", normalized)
    return normalized


def _make_field_meta() -> dict[str, dict[str, object]]:
    """Build default field metadata structure.

    Returns:
    --------
        dict[str, dict[str, object]]:
            Per-field metadata map.
    """
    meta: dict[str, dict[str, object]] = {}
    for key, value in DEFAULT_FIELDS.items():
        meta[key] = {
            "value": value,
            "confidence": 0.0,
            "source": "default",
        }
    return meta


def _set_field(
    result: dict,
    field_meta: dict[str, dict[str, object]],
    field: str,
    value,
    confidence: float,
    source: str,
    normalized_from: Optional[str] = None,
) -> None:
    """Update parsed field value and corresponding metadata.

    Args:
    -----
        result (dict):
            Mutable parsed result map.
        field_meta (dict[str, dict[str, object]]):
            Mutable metadata map.
        field (str):
            Field name to update.
        value:
            Parsed field value.
        confidence (float):
            Confidence score in range [0, 1].
        source (str):
            Parsing source hint.
        normalized_from (Optional[str]):
            Optional raw snippet used for parsing.
    """
    result[field] = value
    entry: dict[str, object] = {
        "value": value,
        "confidence": max(0.0, min(1.0, float(confidence))),
        "source": source,
    }
    if normalized_from:
        entry["normalized_from"] = normalized_from
    field_meta[field] = entry


def _parse_brand(normalized_text: str) -> Optional[tuple[str, str]]:
    """Extract brand candidate from leading lines.

    Args:
    -----
        normalized_text (str):
            Normalized OCR text.

    Returns:
    --------
        Optional[tuple[str, str]]:
            Pair of parsed brand and source snippet.
    """
    for canonical, pattern in BRAND_PATTERNS:
        known = pattern.search(normalized_text)
        if known:
            return canonical, known.group(0)

    lines = [line.strip() for line in normalized_text.splitlines() if line.strip()]
    excluded_tokens = {
        "color",
        "colour",
        "temp",
        "temperature",
        "weight",
        "net",
        "diameter",
        "bed",
        "nozzle",
        "printing",
        "made in",
    }
    for line in lines[:6]:
        clean = re.sub(r"[^A-Za-z0-9 ]", "", line).strip()
        if len(clean) < 3 or len(clean) > 28:
            continue
        lower_clean = clean.lower()
        if any(token in lower_clean for token in excluded_tokens):
            continue
        alnum = re.sub(r"\s+", "", clean)
        if alnum:
            digit_ratio = sum(ch.isdigit() for ch in alnum) / len(alnum)
            if digit_ratio >= 0.2:
                continue
        if re.search(r"\b\d{3,}[-_][A-Z0-9\-]{3,}\b", clean, re.IGNORECASE):
            continue
        if re.search(r"\b[A-Z]{2,}\d{3,}[A-Z0-9]*\b", clean):
            continue
        if re.search(r"\b(\d+(?:\.\d+)?)\s*(mm|g|kg|c)\b", clean, re.IGNORECASE):
            continue
        if any(pattern.search(clean) for _, pattern in MATERIAL_PATTERNS):
            continue
        if re.fullmatch(r"[A-Z0-9 ]+", clean) or clean.istitle():
            return clean.title(), line
    return None


def _parse_material(normalized_text: str) -> Optional[tuple[str, str]]:
    """Extract material by prioritized token patterns.

    Args:
    -----
        normalized_text (str):
            Normalized OCR text.

    Returns:
    --------
        Optional[tuple[str, str]]:
            Parsed material and matched snippet.
    """
    for material, pattern in MATERIAL_PATTERNS:
        match = pattern.search(normalized_text)
        if match:
            return material, match.group(0)
    return None


def _parse_diameter(normalized_text: str) -> Optional[tuple[float, str]]:
    """Parse filament diameter in millimeters.

    Args:
    -----
        normalized_text (str):
            Normalized OCR text.

    Returns:
    --------
        Optional[tuple[float, str]]:
            Parsed diameter and source snippet.
    """
    match = re.search(r"\b([1-3](?:[\.,]\d{1,2}))\s*mm\b", normalized_text, re.IGNORECASE)
    if not match:
        return None
    value = float(match.group(1).replace(",", "."))
    if 1.0 <= value <= 3.5:
        return value, match.group(0)
    return None


def _parse_color(normalized_text: str) -> Optional[tuple[str, str, str]]:
    """Parse color name and hex value.

    Args:
    -----
        normalized_text (str):
            Normalized OCR text.

    Returns:
    --------
        Optional[tuple[str, str, str]]:
            Color name, hex value and source snippet.
    """
    label_match = re.search(
        r"\b(?:colou?r|farbe)\s*[:\-]?\s*([A-Za-zÄÖÜäöüß][A-Za-zÄÖÜäöüß ]{1,24})",
        normalized_text,
        re.IGNORECASE,
    )
    candidates: list[tuple[str, str]] = []
    if label_match:
        label_value = label_match.group(1).strip().lower()
        if any(pattern.search(label_value) for _, pattern in MATERIAL_PATTERNS):
            label_value = ""
        if label_value:
            candidates.append((label_value, label_match.group(0)))

    lower_text = normalized_text.lower()
    for alias, canonical in COLOR_ALIASES.items():
        if alias in lower_text:
            candidates.append((canonical, alias))
    for name in COLOR_MAP:
        if re.search(rf"\b{re.escape(name)}\b", lower_text):
            candidates.append((name, name))

    for name, source in candidates:
        canonical = COLOR_ALIASES.get(name, name)
        if canonical in COLOR_MAP:
            return canonical.title(), COLOR_MAP[canonical], source

    # Fuzzy fallback for common OCR confusion, e.g. "biack" -> "black".
    token_candidates = re.findall(r"[A-Za-zÄÖÜäöüß]{3,20}", lower_text)
    best_name = ""
    best_score = 0.0
    for token in token_candidates:
        for canonical in COLOR_MAP:
            score = SequenceMatcher(None, token, canonical).ratio()
            if score > best_score:
                best_name = canonical
                best_score = score
    if best_name and best_score >= 0.84:
        return best_name.title(), COLOR_MAP[best_name], f"fuzzy:{best_name}"
    return None


def _extract_temperature_range(normalized_text: str, keywords: str) -> Optional[tuple[int, int, str]]:
    """Extract an explicit temperature range for a keyword group.

    Args:
    -----
        normalized_text (str):
            Normalized OCR text.
        keywords (str):
            Alternation regex for field-specific labels.

    Returns:
    --------
        Optional[tuple[int, int, str]]:
            Min temp, max temp and source snippet.
    """
    patterns = [
        re.compile(
            rf"(?:{keywords})\s*temp(?:erature)?\s*[:\-]?\s*(\d{{2,3}})\s*(?:°?\s*C)?\s*(?:-|to|~)\s*(\d{{2,3}})\s*(?:°?\s*C)?",
            re.IGNORECASE,
        ),
        re.compile(
            rf"(?:{keywords})[^\d]{{0,20}}(\d{{2,3}})\s*(?:°?\s*C)?\s*(?:-|to|~)\s*(\d{{2,3}})\s*(?:°?\s*C)?",
            re.IGNORECASE,
        ),
    ]
    for pattern in patterns:
        match = pattern.search(normalized_text)
        if not match:
            continue
        low = int(match.group(1))
        high = int(match.group(2))
        if low > high:
            low, high = high, low
        return low, high, match.group(0)
    return None


def _parse_temperature_fallback(
    normalized_text: str,
    temp_min: int,
    temp_max: int,
) -> Optional[tuple[int, int, str]]:
    """Extract fallback temperature range from generic candidates.

    Args:
    -----
        normalized_text (str):
            Normalized OCR text.
        temp_min (int):
            Inclusive lower plausible bound.
        temp_max (int):
            Inclusive upper plausible bound.

    Returns:
    --------
        Optional[tuple[int, int, str]]:
            Min temp, max temp and source marker.
    """
    candidates = [
        int(v)
        for v in re.findall(r"\b(\d{2,3})\b", normalized_text)
        if temp_min <= int(v) <= temp_max
    ]
    if len(candidates) >= 2:
        return min(candidates), max(candidates), "fallback-candidates"
    if len(candidates) == 1:
        return candidates[0], candidates[0], "fallback-single"
    return None


def _parse_weight(normalized_text: str) -> Optional[tuple[int, str]]:
    """Extract net weight in grams.

    Args:
    -----
        normalized_text (str):
            Normalized OCR text.

    Returns:
    --------
        Optional[tuple[int, str]]:
            Weight in grams and source snippet.
    """
    patterns = [
        re.compile(r"\bnet\s*weight\s*[:\-]?\s*(\d+(?:[\.,]\d+)?)\s*(kg|g)\b", re.IGNORECASE),
        re.compile(r"\b(\d+(?:[\.,]\d+)?)\s*(kg|g)\b", re.IGNORECASE),
    ]
    for pattern in patterns:
        match = pattern.search(normalized_text)
        if not match:
            continue
        raw_value = float(match.group(1).replace(",", "."))
        unit = match.group(2).lower()
        grams = int(round(raw_value * 1000)) if unit == "kg" else int(round(raw_value))
        if 100 <= grams <= 5000:
            return grams, match.group(0)
    return None


def _score_ocr_text(candidate: str) -> float:
    """Score OCR candidate text by quality and relevance.

    Args:
    -----
        candidate (str):
            OCR candidate text.

    Returns:
    --------
        float:
            Heuristic quality score.
    """
    stripped = candidate.strip()
    if not stripped:
        return 0.0
    normalized = _normalize_text(stripped)
    quality_hits = [
        r"\b(?:PLA|PETG|ABS|ASA|TPU|NYLON)\b",
        r"\b(?:NET\s*WEIGHT|WEIGHT)\b",
        r"\b(?:MM)\b",
        r"\b(?:TEMP|NOZZLE|BED)\b",
    ]
    keyword_score = sum(bool(re.search(pattern, normalized, re.IGNORECASE)) for pattern in quality_hits)
    alnum_chars = sum(ch.isalnum() for ch in normalized)
    return keyword_score * 25 + min(alnum_chars, 500) * 0.1


def normalize_match_token(value: str) -> str:
    """Normalize string tokens for fuzzy matching.

    Args:
    -----
        value (str):
            Raw candidate token.

    Returns:
    --------
        str:
            Normalized token.
    """
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKD", value)
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = normalized.lower()
    normalized = normalized.replace("0", "o").replace("1", "l")
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _token_overlap_score(a: str, b: str) -> float:
    """Compute token-overlap score between two normalized strings.

    Args:
    -----
        a (str):
            Normalized source token.
        b (str):
            Normalized candidate token.

    Returns:
    --------
        float:
            Overlap score in range [0, 1].
    """
    a_tokens = set(a.split())
    b_tokens = set(b.split())
    if not a_tokens or not b_tokens:
        return 0.0
    overlap = len(a_tokens & b_tokens)
    return overlap / max(len(a_tokens), len(b_tokens))


def _fuzzy_score(a: str, b: str) -> float:
    """Compute combined fuzzy score for normalized strings.

    Args:
    -----
        a (str):
            Normalized source token.
        b (str):
            Normalized candidate token.

    Returns:
    --------
        float:
            Similarity score in range [0, 1].
    """
    seq_score = SequenceMatcher(None, a, b).ratio()
    token_score = _token_overlap_score(a, b)
    return (seq_score * 0.7) + (token_score * 0.3)


def _best_match(
    raw_value: str,
    candidates: list[tuple[str, str]],
) -> tuple[str, float, str]:
    """Find best canonical candidate for a raw OCR value.

    Args:
    -----
        raw_value (str):
            OCR-extracted value.
        candidates (list[tuple[str, str]]):
            Pairs of (candidate value, source kind).

    Returns:
    --------
        tuple[str, float, str]:
            Matched value, similarity score and source kind.
    """
    if not raw_value or not candidates:
        return raw_value, 0.0, "none"
    raw_norm = normalize_match_token(raw_value)
    if not raw_norm:
        return raw_value, 0.0, "none"

    best_value = raw_value
    best_score = -1.0
    best_source = "none"
    for candidate, source_kind in candidates:
        candidate_norm = normalize_match_token(candidate)
        if not candidate_norm:
            continue
        score = _fuzzy_score(raw_norm, candidate_norm)
        if score > best_score:
            best_value = candidate
            best_score = score
            best_source = source_kind
    return best_value, max(best_score, 0.0), best_source


def _hex_to_color_name(hex_color: str) -> Optional[str]:
    """Map a hex color to canonical color name if known.

    Args:
    -----
        hex_color (str):
            Color hex string.

    Returns:
    --------
        Optional[str]:
            Canonical color name or None.
    """
    if not hex_color:
        return None
    color_hex = hex_color.strip().upper()
    for name, mapped in COLOR_MAP.items():
        if mapped.upper() == color_hex:
            return name.title()
    return None


def apply_db_similarity_matching(
    parsed: dict,
    db_brands: list[str],
    db_materials: list[str],
    db_color_names: list[str],
) -> dict:
    """Apply DB-assisted canonical matching to OCR text fields.

    Args:
    -----
        parsed (dict):
            Parsed OCR payload.
        db_brands (list[str]):
            Brand candidates from DB.
        db_materials (list[str]):
            Material candidates from DB.
        db_color_names (list[str]):
            Color-name candidates from DB.

    Returns:
    --------
        dict:
            Updated payload with canonicalized brand/material/color fields.
    """
    field_meta = parsed.setdefault("field_meta", {})
    warnings = parsed.setdefault("warnings", [])

    brand_candidates = [(value, "db") for value in db_brands if value]
    brand_candidates += [(value, "static") for value in STATIC_BRAND_CANONICALS]

    material_candidates = [(value, "db") for value in db_materials if value]
    material_candidates += [(value, "static") for value, _ in MATERIAL_PATTERNS]

    color_candidates = [(value, "db") for value in db_color_names if value]
    color_candidates += [(value.title(), "static") for value in COLOR_MAP.keys()]

    brand_ocr = str(parsed.get("brand") or "").strip()
    if brand_ocr:
        brand_match, brand_score, brand_source = _best_match(brand_ocr, brand_candidates)
        parsed["canonical_brand"] = brand_match
        brand_match_applied = brand_score >= BRAND_APPLY_THRESHOLD
        final_brand = brand_match if brand_match_applied else brand_ocr
        parsed["brand"] = final_brand
        entry = field_meta.get("brand", {})
        entry.update(
            {
                "value": final_brand,
                "source": "ocr+db-match",
                "confidence": max(float(entry.get("confidence", 0.0)), brand_score),
                "ocr_value": brand_ocr,
                "matched_value": brand_match,
                "match_score": round(brand_score, 3),
                "match_source": brand_source,
                "match_applied": brand_match_applied,
                "match_threshold": BRAND_APPLY_THRESHOLD,
            }
        )
        field_meta["brand"] = entry
        if not brand_match_applied:
            warnings.append("Brand-Match unsicher, OCR-Wert beibehalten")

    material_ocr = str(parsed.get("material") or "").strip()
    if material_ocr:
        material_match, material_score, material_source = _best_match(material_ocr, material_candidates)
        parsed["canonical_material"] = material_match
        parsed["material"] = material_match
        entry = field_meta.get("material", {})
        entry.update(
            {
                "value": material_match,
                "source": "ocr+db-match",
                "confidence": max(float(entry.get("confidence", 0.0)), material_score),
                "ocr_value": material_ocr,
                "matched_value": material_match,
                "match_score": round(material_score, 3),
                "match_source": material_source,
            }
        )
        field_meta["material"] = entry
        if material_score < 0.6:
            warnings.append("Material auto-korrigiert mit niedriger Sicherheit")

    color_ocr = str(parsed.get("color_name") or "").strip()
    if not color_ocr:
        color_ocr = _hex_to_color_name(parsed.get("color") or "") or ""
    if color_ocr:
        color_match, color_score, color_source = _best_match(color_ocr, color_candidates)
        canonical_color_hex = COLOR_MAP.get(color_match.lower())
        if canonical_color_hex:
            parsed["canonical_color_name"] = color_match
            parsed["color_name"] = color_match
            parsed["color"] = canonical_color_hex

            color_name_entry = field_meta.get("color_name", {})
            color_name_entry.update(
                {
                    "value": color_match,
                    "source": "ocr+db-match",
                    "confidence": max(float(color_name_entry.get("confidence", 0.0)), color_score),
                    "ocr_value": color_ocr,
                    "matched_value": color_match,
                    "match_score": round(color_score, 3),
                    "match_source": color_source,
                }
            )
            field_meta["color_name"] = color_name_entry

            color_entry = field_meta.get("color", {})
            color_entry.update(
                {
                    "value": canonical_color_hex,
                    "source": "ocr+db-match",
                    "confidence": max(float(color_entry.get("confidence", 0.0)), color_score),
                    "ocr_value": color_ocr,
                    "matched_value": color_match,
                    "match_score": round(color_score, 3),
                    "match_source": color_source,
                }
            )
            field_meta["color"] = color_entry
            if color_score < 0.6:
                warnings.append("Farbe auto-korrigiert mit niedriger Sicherheit")

    # Deduplicate warning messages while preserving order.
    seen: set[str] = set()
    parsed["warnings"] = [msg for msg in warnings if not (msg in seen or seen.add(msg))]
    return parsed


def parse_label(text: str) -> dict:
    """Parse OCR text from a spool label into structured filament fields.

    Args:
    -----
        text (str):
            Raw text extracted from OCR.

    Returns:
    --------
        dict:
            Parsed spool fields including metadata and warnings.
    """
    normalized_text = _normalize_text(text)
    result = dict(DEFAULT_FIELDS)
    field_meta = _make_field_meta()
    warnings: list[str] = []

    brand = _parse_brand(normalized_text)
    if brand:
        _set_field(result, field_meta, "brand", brand[0], 0.75, "brand-line", brand[1])
    else:
        warnings.append("Brand konnte nicht sicher erkannt werden")

    material = _parse_material(normalized_text)
    if material:
        _set_field(result, field_meta, "material", material[0], 0.92, "material-token", material[1])
    else:
        warnings.append("Material nicht erkannt")

    diameter = _parse_diameter(normalized_text)
    if diameter:
        _set_field(result, field_meta, "diameter", diameter[0], 0.86, "diameter-mm", diameter[1])
    else:
        warnings.append("Durchmesser nicht erkannt")

    color = _parse_color(normalized_text)
    if color:
        _set_field(result, field_meta, "color_name", color[0], 0.74, "color-token", color[2])
        _set_field(result, field_meta, "color", color[1], 0.74, "color-token", color[2])
    else:
        warnings.append("Farbe nicht klar erkannt")

    nozzle_range = _extract_temperature_range(
        normalized_text,
        keywords=r"printing|print|nozzle|extruder",
    ) or _parse_temperature_fallback(normalized_text, 150, 350)
    if nozzle_range:
        source_conf = 0.84 if nozzle_range[2] != "fallback-candidates" else 0.55
        _set_field(result, field_meta, "nozzle_min", nozzle_range[0], source_conf, "nozzle", nozzle_range[2])
        _set_field(result, field_meta, "nozzle_max", nozzle_range[1], source_conf, "nozzle", nozzle_range[2])
    else:
        warnings.append("Nozzle-Temperatur nicht erkannt")

    bed_range = _extract_temperature_range(
        normalized_text,
        keywords=r"bed|plate",
    ) or _parse_temperature_fallback(normalized_text, 30, 130)
    if bed_range:
        source_conf = 0.8 if bed_range[2] != "fallback-candidates" else 0.5
        _set_field(result, field_meta, "bed_min", bed_range[0], source_conf, "bed", bed_range[2])
        _set_field(result, field_meta, "bed_max", bed_range[1], source_conf, "bed", bed_range[2])
    else:
        warnings.append("Bed-Temperatur nicht erkannt")

    weight = _parse_weight(normalized_text)
    if weight:
        _set_field(result, field_meta, "weight_g", weight[0], 0.9, "weight-token", weight[1])
    else:
        warnings.append("Gewicht nicht erkannt")

    result["raw_text"] = text
    result["normalized_text"] = normalized_text
    result["field_meta"] = field_meta
    result["warnings"] = warnings
    return result


def ocr_image(image_bytes: bytes) -> Optional[str]:
    """Run hybrid OCR and return extracted text for legacy callers.

    Args:
    -----
        image_bytes (bytes):
            Encoded image content.

    Returns:
    --------
        Optional[str]:
            Highest-quality OCR candidate text.
    """
    result = ocr_image_with_engine(image_bytes)
    return None if result is None else result.text


@dataclass
class OCRResult:
    """OCR output with source engine and quality score."""

    text: str
    engine: str
    score: float


class OCREngine:
    """Base OCR engine contract."""

    name = "unknown"

    def extract_text(self, image) -> list[str]:
        """Extract text candidates from one image variant.

        Args:
        -----
            image:
                PIL image input.

        Returns:
        --------
            list[str]:
                Candidate OCR outputs for scoring.
        """
        raise NotImplementedError


class TesseractOCREngine(OCREngine):
    """Tesseract-based OCR engine."""

    name = "tesseract"

    def extract_text(self, image) -> list[str]:
        """Extract OCR candidates using different Tesseract PSM modes.

        Args:
        -----
            image:
                PIL image input.

        Returns:
        --------
            list[str]:
                OCR candidates.
        """
        import pytesseract

        return [
            pytesseract.image_to_string(image, config="--oem 3 --psm 6 -l eng"),
            pytesseract.image_to_string(image, config="--oem 3 --psm 4 -l eng"),
            pytesseract.image_to_string(image, config="--oem 3 --psm 11 -l eng"),
            pytesseract.image_to_string(image, config="--oem 1 --psm 6 -l eng"),
        ]


class PaddleOCREngine(OCREngine):
    """PaddleOCR-based engine for robust printed text extraction."""

    name = "paddle"

    def __init__(self) -> None:
        """Initialize PaddleOCR model lazily.

        Raises:
        -------
            RuntimeError:
                Raised when PaddleOCR is unavailable.
        """
        try:
            from paddleocr import PaddleOCR
        except Exception as exc:
            raise RuntimeError("PaddleOCR not available") from exc
        self._ocr = PaddleOCR(use_angle_cls=True, lang="en", use_gpu=False, show_log=False)

    def extract_text(self, image) -> list[str]:
        """Extract text candidates from PaddleOCR output lines.

        Args:
        -----
            image:
                PIL image input.

        Returns:
        --------
            list[str]:
                One joined-text candidate.
        """
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


def _get_paddle_engine() -> Optional[PaddleOCREngine]:
    """Return a cached PaddleOCR engine instance when available.

    Returns:
    --------
        Optional[PaddleOCREngine]:
            Reused Paddle engine instance, or None when unavailable.
    """
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


def _open_image_from_bytes(image_bytes: bytes):
    """Open uploaded bytes as PIL image with optional HEIC support.

    Args:
    -----
        image_bytes (bytes):
            Encoded image content.

    Returns:
    --------
        PIL.Image.Image:
            Opened image object.

    Raises:
    -------
        Exception:
            Raised when the bytes cannot be decoded as image.
    """
    import io
    from PIL import Image

    try:
        import pillow_heif

        pillow_heif.register_heif_opener()
    except Exception:
        # HEIC support is optional and only enabled when dependency is installed.
        pass

    return Image.open(io.BytesIO(image_bytes))


def _crop_bright_label_region(image):
    """Try to crop image to a bright label-like bounding box.

    Args:
    -----
        image:
            PIL image.

    Returns:
    --------
        PIL.Image:
            Cropped or original image.
    """
    gray = image.convert("L")
    # Keep only very bright pixels, then extract bounding box.
    mask = gray.point(lambda p: 255 if p >= 180 else 0)
    bbox = mask.getbbox()
    if not bbox:
        return image
    x1, y1, x2, y2 = bbox
    if (x2 - x1) < image.width * 0.25 or (y2 - y1) < image.height * 0.2:
        return image
    pad_x = int((x2 - x1) * 0.04)
    pad_y = int((y2 - y1) * 0.06)
    left = max(0, x1 - pad_x)
    top = max(0, y1 - pad_y)
    right = min(image.width, x2 + pad_x)
    bottom = min(image.height, y2 + pad_y)
    return image.crop((left, top, right, bottom))


def _build_image_variants(image):
    """Build OCR-friendly preprocessed image variants.

    Args:
    -----
        image:
            Source PIL image.

    Returns:
    --------
        list:
            Prepared PIL variants.
    """
    from PIL import ImageEnhance, ImageFilter, ImageOps

    base = ImageOps.exif_transpose(image)
    width, height = base.size
    scale = max(1.0, 2200 / max(width, height))
    if scale > 1.0:
        from PIL import Image

        base = base.resize((int(width * scale), int(height * scale)), Image.Resampling.LANCZOS)

    cropped = _crop_bright_label_region(base)
    variants = [base, cropped]
    prepared = []
    for variant in variants:
        prepared.append(variant)
        gray = variant.convert("L")
        sharp = ImageEnhance.Sharpness(gray).enhance(2.0)
        contrast = ImageEnhance.Contrast(sharp).enhance(2.4).filter(ImageFilter.SHARPEN)
        threshold_mid = contrast.point(lambda p: 255 if p > 148 else 0)
        threshold_low = contrast.point(lambda p: 255 if p > 132 else 0)
        auto = ImageOps.autocontrast(gray, cutoff=1)
        prepared.extend([gray, auto, contrast, threshold_mid, threshold_low])
    return prepared


def _best_engine_result(engine: OCREngine, variants: list) -> Optional[OCRResult]:
    """Run one OCR engine on prepared variants and return best scored text.

    Args:
    -----
        engine (OCREngine):
            OCR backend instance.
        variants (list):
            Preprocessed PIL image variants.

    Returns:
    --------
        Optional[OCRResult]:
            Best OCR result for the engine.
    """
    best_result: Optional[OCRResult] = None
    for image in variants:
        try:
            candidates = engine.extract_text(image)
        except Exception as exc:
            logger.debug("OCR engine %s failed on variant: %s", engine.name, exc)
            continue
        for text in candidates:
            score = _score_ocr_text(text)
            if best_result is None or score > best_result.score:
                best_result = OCRResult(text=text, engine=engine.name, score=score)
    return best_result


def ocr_image_with_engine(image_bytes: bytes) -> Optional[OCRResult]:
    """Run hybrid OCR and return best text with engine metadata.

    Args:
    -----
        image_bytes (bytes):
            Encoded image content.

    Returns:
    --------
        Optional[OCRResult]:
            Best OCR result and selected engine.
    """
    try:
        image = _open_image_from_bytes(image_bytes)
        variants = _build_image_variants(image)
    except Exception as exc:
        logger.error("OCR preprocessing error: %s", exc)
        return None

    paddle_result: Optional[OCRResult] = None
    paddle_engine = _get_paddle_engine()
    if paddle_engine is not None:
        paddle_result = _best_engine_result(paddle_engine, variants)

    if paddle_result and paddle_result.score >= OCR_FALLBACK_MIN_SCORE:
        logger.info(
            "OCR extracted %s chars via %s (score %.1f)",
            len(paddle_result.text),
            paddle_result.engine,
            paddle_result.score,
        )
        return paddle_result

    tesseract_result = _best_engine_result(TesseractOCREngine(), variants)
    if tesseract_result:
        logger.info(
            "OCR extracted %s chars via %s (score %.1f)",
            len(tesseract_result.text),
            tesseract_result.engine,
            tesseract_result.score,
        )
        return tesseract_result

    if paddle_result:
        logger.info(
            "OCR used low-score %s output (score %.1f) due to missing fallback",
            paddle_result.engine,
            paddle_result.score,
        )
        return paddle_result
    return None
