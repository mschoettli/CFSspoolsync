from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "CFSspoolsync-v3"
    timezone: str = "Europe/Zurich"
    language: str = "de"
    datetime_locale: str = "de-DE"
    ui_theme: str = "dark"
    settings_admin_token: str = ""
    database_url: str = "postgresql+psycopg2://cfs:cfs@db:5432/cfsspoolsync"
    moonraker_url: str = "http://192.168.178.192:7125"
    telemetry_poll_seconds: float = 2.0
    telemetry_offline_grace_cycles: int = 3
    cors_allow_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    default_filament_diameter_mm: float = 1.75
    default_filament_density: float = 1.24
    max_filament_raw_delta_mm: float = 4000.0

    cfs_agent_url: str = ""
    cfs_agent_token: str = ""

    camera_stream_url: str = ""
    camera_webrtc_signal_url: str = ""

    ocr_enable_cloud_fallback: bool = True
    ocr_provider_1: str = "openai"
    ocr_provider_2: str = "claude"
    openai_api_key: str = ""
    anthropic_api_key: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
