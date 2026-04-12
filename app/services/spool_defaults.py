"""Brand-based default values for spool calibration inputs."""

from typing import Optional


_BRAND_DEFAULT_TARE_G = {
    "bambu lab": 246.0,
    "creality": 175.0,
    "esun": 245.0,
    "geeetech": 185.0,
    "jayo": 190.0,
    "sunlu": 190.0,
}

_MATERIAL_TARE_ADJUST_G = {
    "tpu": 15.0,
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


def get_default_tare_weight_g(brand: Optional[str], material: Optional[str]) -> Optional[float]:
    """Return a default empty-spool tare weight for a known brand.

    Args:
    -----
        brand (Optional[str]):
            Spool brand.
        material (Optional[str]):
            Spool material.

    Returns:
    --------
        Optional[float]:
            Suggested tare weight in grams, or ``None`` for unknown brands.
    """
    base = _BRAND_DEFAULT_TARE_G.get(normalize_brand(brand))
    if base is None:
        return None
    material_key = normalize_material(material)
    adjustment = _MATERIAL_TARE_ADJUST_G.get(material_key, 0.0)
    return round(base + adjustment, 1)
