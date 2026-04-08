"""Unit tests for service-layer helper functions."""

from app.services.label_ocr import parse_label
from app.services.ssh_client import meters_to_grams


def test_meters_to_grams_non_positive_returns_zero() -> None:
    """Ensure invalid geometric inputs return zero consumption.

    Returns:
    --------
        None:
            Asserts guard-clause behavior.
    """
    assert meters_to_grams(0, 1.75, 1.24) == 0.0
    assert meters_to_grams(10, 0, 1.24) == 0.0
    assert meters_to_grams(10, 1.75, 0) == 0.0


def test_meters_to_grams_positive_value() -> None:
    """Ensure conversion returns positive grams for valid input.

    Returns:
    --------
        None:
            Asserts physically plausible output.
    """
    value = meters_to_grams(5.0, 1.75, 1.24)
    assert value > 0


def test_parse_label_extracts_core_fields() -> None:
    """Validate OCR text parsing for core filament fields.

    Returns:
    --------
        None:
            Asserts material, diameter and weight extraction.
    """
    text = """
    SUNLU
    PLA+
    Color: White
    Printing Temp: 200-220C
    Bed Temp: 50-60C
    1.75mm
    Net Weight: 1KG
    """
    parsed = parse_label(text)

    assert parsed["brand"] == "Sunlu"
    assert parsed["material"] == "PLA+"
    assert parsed["diameter"] == 1.75
    assert parsed["weight_g"] == 1000
    assert "field_meta" in parsed
    assert "warnings" in parsed
    assert parsed["field_meta"]["weight_g"]["confidence"] > 0.5


def test_parse_label_normalizes_symbols_and_parses_temps() -> None:
    """Validate parser normalization for degree and dash OCR artifacts.

    Returns:
    --------
        None:
            Asserts robust parsing of malformed OCR symbols.
    """
    text = (
        "PLA\n"
        "Printing Temp: 21O\u00b0C \u2013 23O\u00b0C\n"
        "Bed Temp: 6O\u00b0C \u2013 7O\u00b0C\n"
    )
    parsed = parse_label(text)

    assert parsed["nozzle_min"] == 210
    assert parsed["nozzle_max"] == 230
    assert parsed["bed_min"] == 60
    assert parsed["bed_max"] == 70


def test_parse_label_avoids_material_substring_false_positive() -> None:
    """Ensure short material tokens do not match as plain substrings.

    Returns:
    --------
        None:
            Asserts PA is only extracted from token boundaries.
    """
    parsed = parse_label("SPACE GRAY EDITION")
    assert parsed["material"] == ""


def test_parse_label_extracts_known_brand_and_german_color() -> None:
    """Ensure known brand and localized color labels are parsed.

    Returns:
    --------
        None:
            Asserts brand/color extraction for common real-world labels.
    """
    text = """
    BAMBU LAB
    PLA Basic
    Farbe: Weiss
    1.75mm
    Net Weight: 1kg
    """
    parsed = parse_label(text)

    assert parsed["brand"] == "Bambu Lab"
    assert parsed["color_name"] == "White"
    assert parsed["color"] == "#FFFFFF"


def test_parse_label_does_not_use_material_as_color() -> None:
    """Ensure color parser does not accept material tokens as color values.

    Returns:
    --------
        None:
            Asserts color remains default when label value is not a color.
    """
    text = "Color: PLA+"
    parsed = parse_label(text)
    assert parsed["color"] == "#888888"
