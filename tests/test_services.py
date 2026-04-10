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


def test_run_ocr_scan_uses_tesseract_when_required_fields_are_accepted(monkeypatch) -> None:
    """Ensure cloud providers are not used when local OCR is sufficient."""
    local_payload = {
        "engine": "tesseract",
        "duration_ms": 100,
        "raw_text": "PETG 1.75mm 1000g",
        "warnings": [],
        "result": {
            "brand": "Geeetech",
            "material": "PETG",
            "color_name": "White",
            "color_hex": "#FFFFFF",
            "diameter_mm": 1.75,
            "weight_g": 1000,
            "nozzle_min": 220,
            "nozzle_max": 250,
            "bed_min": 60,
            "bed_max": 85,
        },
        "review": {
            "material": {"status": "accepted", "confidence": 0.95},
            "diameter_mm": {"status": "accepted", "confidence": 0.95},
            "weight_g": {"status": "accepted", "confidence": 0.95},
        },
        "fallback_recommended": False,
        "suggestions": {"brand": [], "material": [], "color": []},
        "timing": {"stages": {}},
    }

    monkeypatch.setattr(label_ocr, "_run_tesseract_scan", lambda *_args, **_kwargs: local_payload)
    monkeypatch.setattr(label_ocr, "_provider_order", lambda: ["openai", "claude"])
    monkeypatch.setattr(label_ocr, "OCR_ENABLE_CLOUD_FALLBACK", True)
    monkeypatch.setattr(label_ocr, "_provider_available", lambda _provider: True)

    called = {"count": 0}

    def _never_called(*_args, **_kwargs):
        called["count"] += 1
        return {}

    monkeypatch.setattr(label_ocr, "_call_cloud_provider", _never_called)
    payload = label_ocr.run_ocr_scan(b"dummy", timeout_seconds=2)

    assert payload["provider_used"] == "tesseract"
    assert payload["provider_chain"] == ["tesseract"]
    assert payload["cloud_used"] is False
    assert called["count"] == 0


def test_run_ocr_scan_falls_back_to_openai_when_local_is_incomplete(monkeypatch) -> None:
    """Ensure provider 1 is used when local OCR misses required fields."""
    local_payload = {
        "engine": "tesseract",
        "duration_ms": 80,
        "raw_text": "unknown",
        "warnings": ["material not recognized"],
        "result": {"material": None, "diameter_mm": None, "weight_g": None},
        "review": {
            "material": {"status": "missing", "confidence": 0.0},
            "diameter_mm": {"status": "missing", "confidence": 0.0},
            "weight_g": {"status": "missing", "confidence": 0.0},
        },
        "fallback_recommended": True,
        "suggestions": {"brand": [], "material": [], "color": []},
        "timing": {"stages": {}},
    }
    openai_payload = {
        "raw_text": "{}",
        "warnings": [],
        "result": {"material": "PETG", "diameter_mm": 1.75, "weight_g": 1000},
        "review": {
            "material": {"status": "accepted", "confidence": 0.95},
            "diameter_mm": {"status": "accepted", "confidence": 0.95},
            "weight_g": {"status": "accepted", "confidence": 0.95},
        },
        "fallback_recommended": False,
        "suggestions": {"brand": [], "material": [], "color": []},
        "timing": {"stages": {}},
    }

    monkeypatch.setattr(label_ocr, "_run_tesseract_scan", lambda *_args, **_kwargs: local_payload)
    monkeypatch.setattr(label_ocr, "_provider_order", lambda: ["openai", "claude"])
    monkeypatch.setattr(label_ocr, "OCR_ENABLE_CLOUD_FALLBACK", True)
    monkeypatch.setattr(label_ocr, "_provider_available", lambda _provider: True)
    monkeypatch.setattr(label_ocr, "_call_cloud_provider", lambda provider, *_args, **_kwargs: openai_payload if provider == "openai" else {})

    payload = label_ocr.run_ocr_scan(b"dummy", timeout_seconds=2)

    assert payload["provider_used"] == "openai"
    assert payload["cloud_used"] is True
    assert payload["fallback_reason"] == "missing_required_fields"
    assert payload["provider_chain"] == ["tesseract", "openai"]


def test_run_ocr_scan_uses_provider_two_when_provider_one_fails(monkeypatch) -> None:
    """Ensure provider 2 is used if provider 1 fails."""
    local_payload = {
        "engine": "tesseract",
        "duration_ms": 80,
        "raw_text": "unknown",
        "warnings": ["material not recognized"],
        "result": {"material": None, "diameter_mm": None, "weight_g": None},
        "review": {
            "material": {"status": "missing", "confidence": 0.0},
            "diameter_mm": {"status": "missing", "confidence": 0.0},
            "weight_g": {"status": "missing", "confidence": 0.0},
        },
        "fallback_recommended": True,
        "suggestions": {"brand": [], "material": [], "color": []},
        "timing": {"stages": {}},
    }
    claude_payload = {
        "raw_text": "{}",
        "warnings": [],
        "result": {"material": "PLA", "diameter_mm": 1.75, "weight_g": 1000},
        "review": {
            "material": {"status": "accepted", "confidence": 0.91},
            "diameter_mm": {"status": "accepted", "confidence": 0.91},
            "weight_g": {"status": "accepted", "confidence": 0.91},
        },
        "fallback_recommended": False,
        "suggestions": {"brand": [], "material": [], "color": []},
        "timing": {"stages": {}},
    }

    monkeypatch.setattr(label_ocr, "_run_tesseract_scan", lambda *_args, **_kwargs: local_payload)
    monkeypatch.setattr(label_ocr, "_provider_order", lambda: ["openai", "claude"])
    monkeypatch.setattr(label_ocr, "OCR_ENABLE_CLOUD_FALLBACK", True)
    monkeypatch.setattr(label_ocr, "_provider_available", lambda _provider: True)

    def _provider(provider, *_args, **_kwargs):
        if provider == "openai":
            raise RuntimeError("timeout")
        return claude_payload

    monkeypatch.setattr(label_ocr, "_call_cloud_provider", _provider)
    payload = label_ocr.run_ocr_scan(b"dummy", timeout_seconds=2)

    assert payload["provider_used"] == "claude"
    assert payload["cloud_used"] is True
    assert payload["provider_chain"] == ["tesseract", "openai", "claude"]
    assert any("openai provider failed" in warning for warning in payload["warnings"])
