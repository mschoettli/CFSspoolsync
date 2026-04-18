from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.services.runtime_settings import get_setting, mask_secret, set_setting

router = APIRouter(prefix="/api/settings", tags=["settings"])

SUPPORTED_LANGUAGES = {"de", "en", "fr"}
SUPPORTED_THEMES = {"dark", "light"}


class SettingsPatch(BaseModel):
    language: str | None = None
    theme: str | None = None
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None


def _assert_admin_token(x_admin_token: str | None) -> None:
    required = settings.settings_admin_token.strip()
    if not required:
        return
    if (x_admin_token or "").strip() != required:
        raise HTTPException(status_code=401, detail="invalid admin token")


@router.get("")
def read_settings(db: Session = Depends(get_db)) -> dict:
    language = get_setting(db, "ui.language", settings.language)
    theme = get_setting(db, "ui.theme", settings.ui_theme)
    openai_key = get_setting(db, "api.openai_key", settings.openai_api_key)
    anthropic_key = get_setting(db, "api.anthropic_key", settings.anthropic_api_key)

    return {
        "language": language if language in SUPPORTED_LANGUAGES else settings.language,
        "theme": theme if theme in SUPPORTED_THEMES else settings.ui_theme,
        "openai_api_key_masked": mask_secret(openai_key),
        "anthropic_api_key_masked": mask_secret(anthropic_key),
        "openai_configured": bool(openai_key),
        "anthropic_configured": bool(anthropic_key),
    }


@router.put("")
def update_settings(
    payload: SettingsPatch,
    db: Session = Depends(get_db),
    x_admin_token: str | None = Header(default=None),
) -> dict:
    _assert_admin_token(x_admin_token)
    try:
        if payload.language is not None:
            language = payload.language.strip().lower()
            if language not in SUPPORTED_LANGUAGES:
                raise HTTPException(status_code=422, detail="unsupported language")
            set_setting(db, "ui.language", language, commit=False)

        if payload.theme is not None:
            theme = payload.theme.strip().lower()
            if theme not in SUPPORTED_THEMES:
                raise HTTPException(status_code=422, detail="unsupported theme")
            set_setting(db, "ui.theme", theme, commit=False)

        if payload.openai_api_key is not None:
            set_setting(db, "api.openai_key", payload.openai_api_key.strip(), commit=False)

        if payload.anthropic_api_key is not None:
            set_setting(db, "api.anthropic_key", payload.anthropic_api_key.strip(), commit=False)

        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise

    return read_settings(db)
