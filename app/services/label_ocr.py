import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Material keywords to detect
MATERIAL_KEYWORDS = [
    "PLA", "PETG", "ABS", "ASA", "TPU", "TPE", "NYLON", "PA",
    "PC", "HIPS", "PVA", "CPE", "PP", "PEEK", "CF", "GF"
]

# Color name mapping
COLOR_MAP = {
    "white":   "#FFFFFF",
    "black":   "#000000",
    "red":     "#FF0000",
    "blue":    "#0000FF",
    "green":   "#00AA00",
    "yellow":  "#FFFF00",
    "orange":  "#FF8800",
    "purple":  "#880088",
    "grey":    "#888888",
    "gray":    "#888888",
    "silver":  "#C0C0C0",
    "gold":    "#FFD700",
    "brown":   "#8B4513",
    "pink":    "#FF69B4",
    "cyan":    "#00CCCC",
    "magenta": "#CC00CC",
    "natural": "#F5DEB3",
    "transparent": "#CCCCCC",
}


def parse_label(text: str) -> dict:
    """Parse OCR text from a filament spool label and extract filament data."""
    result = {
        "brand":      "",
        "material":   "",
        "color":      "#888888",
        "color_name": "",
        "nozzle_min": 0,
        "nozzle_max": 0,
        "bed_min":    0,
        "bed_max":    0,
        "diameter":   1.75,
        "weight_g":   1000,
        "raw_text":   text,
    }

    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines:
        return result

    # Brand: usually the first prominent line (all caps, short)
    for line in lines[:4]:
        clean = re.sub(r'[^A-Za-z0-9 ]', '', line).strip()
        if 2 < len(clean) < 30 and clean.upper() == clean and not any(k in clean for k in ["PETG", "PLA", "ABS"]):
            result["brand"] = clean.title()
            break

    # Material
    text_upper = text.upper()
    for mat in MATERIAL_KEYWORDS:
        if mat in text_upper:
            result["material"] = mat
            break

    # Diameter
    m = re.search(r'(\d+\.\d+)\s*mm', text, re.IGNORECASE)
    if m:
        result["diameter"] = float(m.group(1))

    # Color name
    m = re.search(r'[Cc]olo(?:u)?r\s*[:\-]?\s*([A-Za-z]+)', text)
    if m:
        color_name = m.group(1).lower().strip()
        result["color_name"] = color_name.title()
        if color_name in COLOR_MAP:
            result["color"] = COLOR_MAP[color_name]

    # Nozzle / Printing temp
    m = re.search(r'[Pp]rint(?:ing)?\s*[Tt]emp[^:]*[:\s]+(\d{2,3})\s*°?C?\s*[-–]\s*(\d{2,3})', text)
    if m:
        result["nozzle_min"] = int(m.group(1))
        result["nozzle_max"] = int(m.group(2))
    else:
        # Fallback: find two consecutive 3-digit numbers in range 150-350
        matches = re.findall(r'\b(1[5-9]\d|2\d{2}|3[0-4]\d)\b', text)
        if len(matches) >= 2:
            temps = sorted([int(x) for x in matches[:4]])
            nozzle_temps = [t for t in temps if 150 <= t <= 350]
            if len(nozzle_temps) >= 2:
                result["nozzle_min"] = nozzle_temps[0]
                result["nozzle_max"] = nozzle_temps[-1]

    # Bed temp
    m = re.search(r'[Bb]ed\s*[Tt]emp[^:]*[:\s]+(\d{2,3})\s*°?C?\s*[-–]\s*(\d{2,3})', text)
    if m:
        result["bed_min"] = int(m.group(1))
        result["bed_max"] = int(m.group(2))
    else:
        # Fallback: find two consecutive 2-digit numbers in range 40-120
        matches = re.findall(r'\b([4-9]\d|1[0-2]\d)\b', text)
        if len(matches) >= 2:
            bed_temps = sorted([int(x) for x in matches[:4]])
            if len(bed_temps) >= 2:
                result["bed_min"] = bed_temps[0]
                result["bed_max"] = bed_temps[-1]

    # Weight
    m = re.search(r'[Nn]et\s*[Ww]eight\s*[:\s]+(\d+(?:\.\d+)?)\s*(KG|kg|g|G)', text)
    if m:
        val = float(m.group(1))
        unit = m.group(2).lower()
        result["weight_g"] = int(val * 1000) if unit == "kg" else int(val)
    else:
        m = re.search(r'(\d+(?:\.\d+)?)\s*(KG|kg)', text)
        if m:
            result["weight_g"] = int(float(m.group(1)) * 1000)

    return result


def ocr_image(image_bytes: bytes) -> Optional[str]:
    """Run Tesseract OCR on image bytes and return extracted text."""
    try:
        import pytesseract
        from PIL import Image
        import io

        img = Image.open(io.BytesIO(image_bytes))

        # Upscale small images for better OCR
        w, h = img.size
        if w < 800:
            scale = 800 / w
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

        # Convert to grayscale
        img = img.convert("L")

        text = pytesseract.image_to_string(img, config="--psm 6")
        logger.info(f"OCR extracted {len(text)} chars")
        return text

    except Exception as exc:
        logger.error(f"OCR error: {exc}")
        return None
