"""Application configuration routes."""

from fastapi import APIRouter

from app.services.app_locale import resolve_app_config

router = APIRouter(prefix="/api", tags=["app-config"])


@router.get("/app-config")
def get_app_config() -> dict[str, str]:
    """Return public frontend configuration."""
    return resolve_app_config()
