from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.services.runtime_settings import get_setting

router = APIRouter(prefix="/api", tags=["app-config"])


@router.get("/app-config")
def app_config(db: Session = Depends(get_db)) -> dict[str, str]:
    language = get_setting(db, "ui.language", settings.language)
    theme = get_setting(db, "ui.theme", settings.ui_theme)

    return {
        "timezone": settings.timezone,
        "language": language,
        "theme": theme,
        "datetime_locale": settings.datetime_locale,
        "camera_stream_url": settings.camera_stream_url,
    }
