from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(prefix="/api", tags=["app-config"])


@router.get("/app-config")
def app_config() -> dict[str, str]:
    return {
        "timezone": settings.timezone,
        "language": settings.language,
        "datetime_locale": settings.datetime_locale,
        "camera_stream_url": settings.camera_stream_url,
    }
