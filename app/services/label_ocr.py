"""OCR helpers for extracting spool data from label photos."""

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

MATERIAL_KEYWORDS = [
    "PLA", "PETG", "ABS", "ASA", "TPU", "TPE", "NYLON", "PA",
    "PC", "HIPS", "PVA", "CPE", "PP", "PEEK", "CF", "GF",
]

COLOR_MAP = {
    "white": "#FFFFFF",
    "black": "#000000",
    "red": "#FF0000",
    "blue": "#0000FF",
    "green": "#00AA00",
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


def parse_label(text: str) -> dict:
    """Parse OCR text from a spool label into structured filament fields."""
    result = {
        "brand": "",
        "material": "",
        "color": "#888888",
        "color_name": "",
        "nozzle_min": 0,
        "nozzle_max": 0,
        "bed_min": 0,
        "bed_max": 0,
        "diameter": 1.75,
        "weight_g": 1000,
        "raw_text": text,
    }

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return result

    for line in lines[:4]:
        clean = re.sub(r"[^A-Za-z0-9 ]", "", line).strip()
        is_material_line = any(keyword in clean for keyword in ["PETG", "PLA", "ABS"])
        if 2 < len(clean) < 30 and clean.upper() == clean and not is_material_line:
            result["brand"] = clean.title()
            break

    text_upper = text.upper()
    for material in MATERIAL_KEYWORDS:
        if material in text_upper:
            result["material"] = material
            break

    diameter_match = re.search(r"(\d+\.\d+)\s*mm", text, re.IGNORECASE)
    if diameter_match:
        result["diameter"] = float(diameter_match.group(1))

    color_match = re.search(r"[Cc]olo(?:u)?r\s*[:\-]?\s*([A-Za-z]+)", text)
    if color_match:
        color_name = color_match.group(1).lower().strip()
        result["color_name"] = color_name.title()
        if color_name in COLOR_MAP:
            result["color"] = COLOR_MAP[color_name]

    nozzle_match = re.search(
        r"[Pp]rint(?:ing)?\s*[Tt]emp[^:]*[:\s]+(\d{2,3})\s*°?C?\s*[-–]\s*(\d{2,3})",
        text,
    )
    if nozzle_match:
        result["nozzle_min"] = int(nozzle_match.group(1))
        result["nozzle_max"] = int(nozzle_match.group(2))
    else:
        temp_candidates = re.findall(r"\b(1[5-9]\d|2\d{2}|3[0-4]\d)\b", text)
        if len(temp_candidates) >= 2:
            temps = sorted(int(value) for value in temp_candidates[:4])
            nozzle_temps = [value for value in temps if 150 <= value <= 350]
            if len(nozzle_temps) >= 2:
                result["nozzle_min"] = nozzle_temps[0]
                result["nozzle_max"] = nozzle_temps[-1]

    bed_match = re.search(
        r"[Bb]ed\s*[Tt]emp[^:]*[:\s]+(\d{2,3})\s*°?C?\s*[-–]\s*(\d{2,3})",
        text,
    )
    if bed_match:
        result["bed_min"] = int(bed_match.group(1))
        result["bed_max"] = int(bed_match.group(2))
    else:
        bed_candidates = re.findall(r"\b([4-9]\d|1[0-2]\d)\b", text)
        if len(bed_candidates) >= 2:
            bed_temps = sorted(int(value) for value in bed_candidates[:4])
            if len(bed_temps) >= 2:
                result["bed_min"] = bed_temps[0]
                result["bed_max"] = bed_temps[-1]

    weight_match = re.search(r"[Nn]et\s*[Ww]eight\s*[:\s]+(\d+(?:\.\d+)?)\s*(KG|kg|g|G)", text)
    if weight_match:
        value = float(weight_match.group(1))
        unit = weight_match.group(2).lower()
        result["weight_g"] = int(value * 1000) if unit == "kg" else int(value)
    else:
        kilo_match = re.search(r"(\d+(?:\.\d+)?)\s*(KG|kg)", text)
        if kilo_match:
            result["weight_g"] = int(float(kilo_match.group(1)) * 1000)

    return result


def ocr_image(image_bytes: bytes) -> Optional[str]:
    """Run Tesseract OCR on image bytes and return best extracted text."""
    try:
        import io

        from PIL import Image, ImageEnhance, ImageFilter, ImageOps
        import pytesseract

        image = Image.open(io.BytesIO(image_bytes))
        image = ImageOps.exif_transpose(image)

        width, height = image.size
        scale = max(1, 1200 / max(width, height))
        if scale > 1:
            image = image.resize((int(width * scale), int(height * scale)), Image.LANCZOS)

        image = image.convert("L")
        image = ImageEnhance.Contrast(image).enhance(2.0)
        image = ImageEnhance.Sharpness(image).enhance(2.0)
        image = image.filter(ImageFilter.SHARPEN)

        texts = [
            pytesseract.image_to_string(image, config="--psm 6"),
            pytesseract.image_to_string(image, config="--psm 4"),
            pytesseract.image_to_string(image, config="--psm 3"),
        ]
        text = max(texts, key=lambda candidate: len(candidate.strip()))

        logger.info("OCR extracted %s chars", len(text))
        return text
    except Exception as exc:
        logger.error("OCR error: %s", exc)
        return None
