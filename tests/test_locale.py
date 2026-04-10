"""Tests for app locale resolution."""

from app.services import app_locale


def test_resolve_app_locale_german(monkeypatch) -> None:
    """Map Zurich timezone to German locale."""
    monkeypatch.setenv("TIMEZONE", "Europe/Zurich")
    data = app_locale.resolve_app_locale()
    assert data["language"] == "de"
    assert data["datetime_locale"] == "de-DE"


def test_resolve_app_locale_french(monkeypatch) -> None:
    """Map Paris timezone to French locale."""
    monkeypatch.setenv("TIMEZONE", "Europe/Paris")
    data = app_locale.resolve_app_locale()
    assert data["language"] == "fr"
    assert data["datetime_locale"] == "fr-FR"


def test_resolve_app_locale_italian(monkeypatch) -> None:
    """Map Rome timezone to Italian locale."""
    monkeypatch.setenv("TIMEZONE", "Europe/Rome")
    data = app_locale.resolve_app_locale()
    assert data["language"] == "it"
    assert data["datetime_locale"] == "it-IT"


def test_resolve_app_locale_defaults_to_english(monkeypatch) -> None:
    """Fallback unknown timezone to English locale."""
    monkeypatch.setenv("TIMEZONE", "America/New_York")
    data = app_locale.resolve_app_locale()
    assert data["language"] == "en"
    assert data["datetime_locale"] == "en-US"

