"""Application locale resolution from timezone configuration."""

from __future__ import annotations

import os

TIMEZONE_LANGUAGE_MAP: dict[str, str] = {
    "Europe/Zurich": "de",
    "Europe/Berlin": "de",
    "Europe/Vienna": "de",
    "Europe/Paris": "fr",
    "Europe/Brussels": "fr",
    "Europe/Luxembourg": "fr",
    "Europe/Rome": "it",
    "Europe/Vatican": "it",
}

LANGUAGE_DATETIME_LOCALE_MAP: dict[str, str] = {
    "de": "de-DE",
    "en": "en-US",
    "fr": "fr-FR",
    "it": "it-IT",
}


def resolve_app_locale() -> dict[str, str]:
    """Resolve application language and datetime locale from timezone.

    Returns:
    --------
        dict[str, str]:
            Timezone, language, and datetime locale configuration.
    """
    timezone = (os.getenv("TIMEZONE") or "").strip()
    if not timezone:
        timezone = "UTC"

    language = TIMEZONE_LANGUAGE_MAP.get(timezone)
    if language is None:
        if timezone.startswith("Europe/Paris"):
            language = "fr"
        elif timezone.startswith("Europe/Rome"):
            language = "it"
        elif timezone.startswith(("Europe/Zurich", "Europe/Berlin", "Europe/Vienna")):
            language = "de"
        else:
            language = "en"

    datetime_locale = LANGUAGE_DATETIME_LOCALE_MAP.get(language, "en-US")
    return {
        "timezone": timezone,
        "language": language,
        "datetime_locale": datetime_locale,
    }


def resolve_app_config() -> dict[str, str]:
    """Resolve public app configuration from environment values.

    Returns:
    --------
        dict[str, str]:
            Locale and camera stream configuration for the frontend.
    """
    config = resolve_app_locale()
    camera_stream_url = (os.getenv("CAMERA_STREAM_URL") or "").strip()
    config["camera_stream_url"] = camera_stream_url
    return config
