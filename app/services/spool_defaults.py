"""Brand-based default values for spool calibration inputs."""

from typing import Optional

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import TareDefault


STATIC_BRAND_TARE_DEFAULTS = [
    {"brand_key": "bambu lab", "brand_label": "Bambu Lab", "tare_weight_g": 246.0},
    {"brand_key": "creality", "brand_label": "Creality", "tare_weight_g": 175.0},
    {"brand_key": "esun", "brand_label": "eSUN", "tare_weight_g": 245.0},
    {"brand_key": "geeetech", "brand_label": "Geeetech", "tare_weight_g": 185.0},
    {"brand_key": "jayo", "brand_label": "JAYO", "tare_weight_g": 190.0},
    {"brand_key": "sunlu", "brand_label": "SUNLU", "tare_weight_g": 190.0},
]

_BRAND_DEFAULT_TARE_G = {
    item["brand_key"]: item["tare_weight_g"]
    for item in STATIC_BRAND_TARE_DEFAULTS
}

_MATERIAL_TARE_ADJUST_G = {
    "TPU": 15.0,
}


def normalize_brand(value: Optional[str]) -> str:
    """Normalize a brand string for deterministic lookups.

    Args:
    -----
        value (Optional[str]):
            Raw brand value.

    Returns:
    --------
        str:
            Lower-cased and trimmed brand key.
    """
    if not value:
        return ""
    return " ".join(value.strip().lower().split())


def normalize_material(value: Optional[str]) -> str:
    """Normalize a material string for deterministic lookups.

    Args:
    -----
        value (Optional[str]):
            Raw material value.

    Returns:
    --------
        str:
            Upper-cased and trimmed material key.
    """
    if not value:
        return ""
    return value.strip().upper()


def get_default_tare_weight_g(
    brand: Optional[str],
    material: Optional[str],
    db: Optional[Session] = None,
) -> Optional[float]:
    """Return a default empty-spool tare weight for a known brand.

    Args:
    -----
        brand (Optional[str]):
            Spool brand.
        material (Optional[str]):
            Spool material.
        db (Optional[Session]):
            Optional active SQLAlchemy session.

    Returns:
    --------
        Optional[float]:
            Suggested tare weight in grams, or ``None`` for unknown brands.
    """
    base = get_brand_default_tare_weight_g(normalize_brand(brand), db)
    if base is None:
        return None
    material_key = normalize_material(material)
    adjustment = _MATERIAL_TARE_ADJUST_G.get(material_key, 0.0)
    return round(base + adjustment, 1)


def get_brand_default_tare_weight_g(
    brand: Optional[str],
    db: Optional[Session] = None,
) -> Optional[float]:
    """Return the base tare value for one normalized brand key.

    Args:
    -----
        brand (Optional[str]):
            Brand label or normalized key.
        db (Optional[Session]):
            Optional active SQLAlchemy session.

    Returns:
    --------
        Optional[float]:
            Base tare weight in grams, or ``None`` when unknown.
    """
    brand_key = normalize_brand(brand)
    if not brand_key:
        return None

    if db is not None:
        entry = db.query(TareDefault).filter(TareDefault.brand_key == brand_key).first()
        if entry:
            return float(entry.tare_weight_g)
        return _BRAND_DEFAULT_TARE_G.get(brand_key)

    local_session = SessionLocal()
    try:
        entry = (
            local_session
            .query(TareDefault)
            .filter(TareDefault.brand_key == brand_key)
            .first()
        )
        if entry:
            return float(entry.tare_weight_g)
        return _BRAND_DEFAULT_TARE_G.get(brand_key)
    finally:
        local_session.close()
