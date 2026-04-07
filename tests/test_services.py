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
    assert parsed["material"] == "PLA"
    assert parsed["diameter"] == 1.75
    assert parsed["weight_g"] == 1000
