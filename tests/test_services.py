"""Unit tests for service-layer helper functions."""

from app.services import label_ocr_v2
from app.services.label_ocr_v2 import parse_ocr_text_v2
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


def test_parse_v2_geeetech_white_label() -> None:
    """Validate Geeetech-style label parsing."""
    text = (
        "GEEETECH\nPETG 1.75mm Color: White\n"
        "Printing Temp: 220C-250C\nBed Temp:60-85C\nNet Weight:2KG"
    )
    parsed = parse_ocr_text_v2(text)
    fields = parsed["fields"]
    assert fields["brand"] == "Geeetech"
    assert fields["material"] == "PETG"
    assert fields["color_name"] == "White"
    assert fields["color_hex"] == "#FFFFFF"
    assert fields["weight_g"] == 2000
    assert fields["diameter_mm"] == 1.75
    assert fields["nozzle_min"] == 220
    assert fields["nozzle_max"] == 250
    assert fields["bed_min"] == 60
    assert fields["bed_max"] == 85


def test_parse_v2_ender_black_label() -> None:
    """Validate Ender/Creality label parsing."""
    text = (
        "Ender PLA Value Pake\nColor Black\nDiameter 1.75±0.03mm\n"
        "Net Weight 1000g\nNozzle Temp 190-220C\nBed Temp 25-60C"
    )
    parsed = parse_ocr_text_v2(text)
    fields = parsed["fields"]
    assert fields["brand"] == "Creality"
    assert fields["material"] == "PLA"
    assert fields["color_name"] == "Black"
    assert fields["color_hex"] == "#000000"
    assert fields["weight_g"] == 1000
    assert fields["diameter_mm"] == 1.75
    assert fields["nozzle_min"] == 190
    assert fields["nozzle_max"] == 220
    assert fields["bed_min"] == 25
    assert fields["bed_max"] == 60


def test_parse_v2_cr_silk_gold_label() -> None:
    """Validate CR-Silk style label parsing."""
    text = (
        "Product Name CR-Silk\nColor Gold\nDiameter 1.75mm\n"
        "N.W. 1.0kg\nPrint Temp 190-230C"
    )
    parsed = parse_ocr_text_v2(text)
    fields = parsed["fields"]
    assert fields["brand"] == "Creality"
    assert fields["material"] == "PLA"
    assert fields["color_name"] == "Gold"
    assert fields["color_hex"] == "#FFD700"
    assert fields["diameter_mm"] == 1.75
    assert fields["weight_g"] == 1000
    assert fields["nozzle_min"] == 190
    assert fields["nozzle_max"] == 230


def test_parse_v2_jayo_label() -> None:
    """Validate JAYO-like one-line label parsing."""
    text = "JAYO PLA+ 3D Printer Filament 1.75mm 1.1kg Burdy Wood"
    parsed = parse_ocr_text_v2(text)
    fields = parsed["fields"]
    assert fields["brand"] == "JAYO"
    assert fields["material"] == "PLA+"
    assert fields["diameter_mm"] == 1.75
    assert fields["weight_g"] == 1100
    assert fields["color_hex"] == "#8B4513"


def test_parse_v2_keeps_low_confidence_fields_unaccepted() -> None:
    """Ensure low-confidence values are not auto-accepted."""
    parsed = parse_ocr_text_v2("Brand: Xqzv Material: PLS")
    assert parsed["fields"]["brand"] is None
    assert parsed["field_meta"]["brand"]["status"] in {"low_confidence", "missing", "rejected_by_rule"}
    assert parsed["fallback_recommended"] is True
    assert parsed["suggestions"]["material"]


def test_parse_v2_marks_fallback_not_required_when_required_fields_are_accepted() -> None:
    """Ensure fallback hint is disabled when all required fields are accepted."""
    parsed = parse_ocr_text_v2("PETG 1.75mm Net Weight 1000g")
    assert parsed["fields"]["material"] == "PETG"
    assert parsed["fields"]["diameter_mm"] == 1.75
    assert parsed["fields"]["weight_g"] == 1000
    assert parsed["fallback_recommended"] is False


def test_ocr_v2_prefers_paddle_when_score_is_good(monkeypatch) -> None:
    """Ensure paddle result is selected when quality is high."""
    monkeypatch.setattr(label_ocr_v2, "_open_image_from_bytes", lambda _: object())
    monkeypatch.setattr(label_ocr_v2, "_build_variant_sets", lambda _: (["variant"], ["variant"]))

    class DummyPaddleEngine:
        """Minimal paddle stand-in."""

        name = "paddle"

    monkeypatch.setattr(label_ocr_v2, "_get_paddle_engine", lambda: DummyPaddleEngine())
    monkeypatch.setattr(
        label_ocr_v2,
        "_best_result",
        lambda engine, *_args, **_kwargs: (label_ocr_v2.OCRResult("PETG 1.75mm", engine.name, 80.0), 10, False),
    )
    result, _meta = label_ocr_v2._extract_ocr_text(b"dummy")
    assert result.engine == "paddle"


def test_ocr_v2_falls_back_to_tesseract(monkeypatch) -> None:
    """Ensure fallback selects Tesseract when paddle score is low."""
    monkeypatch.setattr(label_ocr_v2, "_open_image_from_bytes", lambda _: object())
    monkeypatch.setattr(label_ocr_v2, "_build_variant_sets", lambda _: (["variant"], ["variant"]))

    class DummyPaddleEngine:
        """Minimal paddle stand-in."""

        name = "paddle"

    monkeypatch.setattr(label_ocr_v2, "_get_paddle_engine", lambda: DummyPaddleEngine())

    def fake_best(engine, _variants, **_kwargs):
        if engine.name == "paddle":
            return label_ocr_v2.OCRResult("noise", "paddle", 10.0), 10, False
        return label_ocr_v2.OCRResult("PETG 1.75mm", "tesseract", 60.0), 10, False

    monkeypatch.setattr(label_ocr_v2, "_best_result", fake_best)
    result, _meta = label_ocr_v2._extract_ocr_text(b"dummy")
    assert result.engine == "tesseract"


def test_run_ocr_v2_returns_empty_payload_when_extraction_fails(monkeypatch) -> None:
    """Ensure OCR v2 returns structured empty payload on extraction failure."""
    monkeypatch.setattr(
        label_ocr_v2,
        "_extract_ocr_text",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("broken engine")),
    )
    payload = label_ocr_v2.run_ocr_v2(b"dummy")
    assert payload["engine"] == "none"
    assert payload["fields"]["material"] is None
    assert payload["field_meta"]["material"]["status"] == "missing"
    assert payload["warnings"]


def test_ocr_v2_fast_pass_can_return_without_deep_pass(monkeypatch) -> None:
    """Ensure fast pass short-circuits deep pass for strong OCR output."""
    monkeypatch.setattr(label_ocr_v2, "_open_image_from_bytes", lambda _: object())
    monkeypatch.setattr(label_ocr_v2, "_build_variant_sets", lambda _: (["fast"], ["deep"]))

    class DummyPaddleEngine:
        """Minimal paddle stand-in."""

        name = "paddle"

    monkeypatch.setattr(label_ocr_v2, "_get_paddle_engine", lambda: DummyPaddleEngine())

    def fake_best(engine, variants, **_kwargs):
        if variants == ["fast"]:
            return label_ocr_v2.OCRResult("PETG 1.75mm", engine.name, 70.0), 10, False
        raise AssertionError("Deep pass should not run")

    monkeypatch.setattr(label_ocr_v2, "_best_result", fake_best)
    _result, meta = label_ocr_v2._extract_ocr_text(b"dummy")
    assert meta.fast_phase_returned is True
    assert meta.deep_pass_ms == 0


def test_ocr_v2_marks_partial_timeout(monkeypatch) -> None:
    """Ensure partial timeout is reported in metadata."""
    monkeypatch.setattr(label_ocr_v2, "_open_image_from_bytes", lambda _: object())
    monkeypatch.setattr(label_ocr_v2, "_build_variant_sets", lambda _: (["fast"], ["deep"]))

    class DummyPaddleEngine:
        """Minimal paddle stand-in."""

        name = "paddle"

    monkeypatch.setattr(label_ocr_v2, "_get_paddle_engine", lambda: DummyPaddleEngine())
    monkeypatch.setattr(
        label_ocr_v2,
        "_best_result",
        lambda _engine, _variants, **_kwargs: (None, 1, True),
    )
    _result, meta = label_ocr_v2._extract_ocr_text(b"dummy", budget_seconds=0.00001)
    assert meta.partial_timeout is True
