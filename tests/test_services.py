"""Unit tests for service-layer helper functions."""

from app.services import label_ocr
from app.services.label_ocr import parse_label_text
from app.services.ssh_client import meters_to_grams


def test_meters_to_grams_non_positive_returns_zero() -> None:
    """Ensure invalid geometric inputs return zero consumption."""
    assert meters_to_grams(0, 1.75, 1.24) == 0.0
    assert meters_to_grams(10, 0, 1.24) == 0.0
    assert meters_to_grams(10, 1.75, 0) == 0.0


def test_meters_to_grams_positive_value() -> None:
    """Ensure conversion returns positive grams for valid input."""
    value = meters_to_grams(5.0, 1.75, 1.24)
    assert value > 0


def test_parse_geeetech_white_label() -> None:
    """Validate Geeetech-style label parsing."""
    text = (
        "GEEETECH\nPETG 1.75mm Color: White\n"
        "Printing Temp: 220C-250C\nBed Temp:60-85C\nNet Weight:2KG"
    )
    parsed = parse_label_text(text)
    result = parsed["result"]
    assert result["brand"] == "Geeetech"
    assert result["material"] == "PETG"
    assert result["color_name"] == "White"
    assert result["color_hex"] == "#FFFFFF"
    assert result["weight_g"] == 2000
    assert result["diameter_mm"] == 1.75
    assert result["nozzle_min"] == 220
    assert result["nozzle_max"] == 250
    assert result["bed_min"] == 60
    assert result["bed_max"] == 85


def test_parse_jayo_one_line_label() -> None:
    """Validate one-line JAYO-like label parsing."""
    text = "JAYO PLA+ 3D Printer Filament 1.75mm 1.1kg Burdy Wood"
    parsed = parse_label_text(text)
    result = parsed["result"]
    assert result["brand"] == "JAYO"
    assert result["material"] == "PLA+"
    assert result["diameter_mm"] == 1.75
    assert result["weight_g"] == 1100
    assert result["color_hex"] == "#8B4513"


def test_parse_recommends_fallback_when_required_fields_missing() -> None:
    """Ensure fallback hint is enabled when required fields are incomplete."""
    parsed = parse_label_text("Brand: Unknown")
    assert parsed["fallback_recommended"] is True
    assert parsed["suggestions"]["material"]


def test_parse_no_fallback_when_required_fields_accepted() -> None:
    """Ensure fallback hint is disabled when required fields are accepted."""
    parsed = parse_label_text("PETG 1.75mm Net Weight 1000g")
    assert parsed["result"]["material"] == "PETG"
    assert parsed["result"]["diameter_mm"] == 1.75
    assert parsed["result"]["weight_g"] == 1000
    assert parsed["fallback_recommended"] is False


def test_run_ocr_scan_returns_payload_even_on_engine_error(monkeypatch) -> None:
    """Ensure OCR scan returns structured response on runtime failures."""
    monkeypatch.setattr(
        label_ocr,
        "_open_image_from_bytes",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("broken")),
    )
    payload = label_ocr.run_ocr_scan(b"dummy", timeout_seconds=3)
    assert payload["engine"] == "tesseract"
    assert payload["result"]["material"] is None
    assert payload["fallback_recommended"] is True
    assert payload["warnings"]

