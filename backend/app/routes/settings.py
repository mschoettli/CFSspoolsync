"""Settings endpoints for language/theme used by external integrations."""
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import AppSetting

router = APIRouter(prefix="/settings", tags=["settings"])

SUPPORTED_LANGUAGES = {"de", "en", "fr", "it", "es", "pt", "nl", "pl"}
SUPPORTED_THEMES = {"dark", "light"}


class SettingsPatch(BaseModel):
    """Accepted payload for settings updates."""

    language: str | None = None
    theme: str | None = None


def _get_setting(db: Session, key: str, default: str) -> str:
    """Return a setting value from DB or a fallback default."""
    row = db.query(AppSetting).filter(AppSetting.key == key).first()
    return (row.value or "").strip() if row else default


def _set_setting(db: Session, key: str, value: str) -> None:
    """Insert or update a setting key with the given value."""
    row = db.query(AppSetting).filter(AppSetting.key == key).first()
    if row:
        row.value = value
        return
    db.add(AppSetting(key=key, value=value))


def _assert_admin_token(x_admin_token: str | None) -> None:
    """Validate optional admin token when configured."""
    required = (settings.settings_admin_token or "").strip()
    if not required:
        return
    if (x_admin_token or "").strip() != required:
        raise HTTPException(status_code=401, detail="invalid admin token")


@router.get("")
def read_settings(db: Session = Depends(get_db)) -> dict:
    """Return current language/theme settings."""
    language = _get_setting(db, "ui.language", settings.ui_language).lower()
    theme = _get_setting(db, "ui.theme", settings.ui_theme).lower()
    if language not in SUPPORTED_LANGUAGES:
        language = settings.ui_language
    if theme not in SUPPORTED_THEMES:
        theme = settings.ui_theme
    return {"language": language, "theme": theme}


@router.put("")
def update_settings(
    payload: SettingsPatch,
    db: Session = Depends(get_db),
    x_admin_token: str | None = Header(default=None),
) -> dict:
    """Update language/theme settings with optional token protection."""
    _assert_admin_token(x_admin_token)
    if payload.language is not None:
        language = payload.language.strip().lower()
        if language not in SUPPORTED_LANGUAGES:
            raise HTTPException(status_code=422, detail="unsupported language")
        _set_setting(db, "ui.language", language)

    if payload.theme is not None:
        theme = payload.theme.strip().lower()
        if theme not in SUPPORTED_THEMES:
            raise HTTPException(status_code=422, detail="unsupported theme")
        _set_setting(db, "ui.theme", theme)

    db.commit()
    return read_settings(db)
