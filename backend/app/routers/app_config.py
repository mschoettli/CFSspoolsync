from fastapi import APIRouter

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.runtime_settings import get_setting

router = APIRouter(prefix="/api", tags=["app-config"])


@router.get("/app-config")
def app_config() -> dict[str, str]:
    db = SessionLocal()
    try:
        language = get_setting(db, "ui.language", settings.language)
        theme = get_setting(db, "ui.theme", settings.ui_theme)
    finally:
        db.close()

    return {
        "timezone": settings.timezone,
        "language": language,
        "theme": theme,
        "datetime_locale": settings.datetime_locale,
        "camera_stream_url": settings.camera_stream_url,
    }
