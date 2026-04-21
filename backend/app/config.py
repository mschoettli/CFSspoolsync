"""Runtime configuration - read from environment variables."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Database
    database_url: str = "sqlite:///./data/cfs.db"

    # CFS / Moonraker bridge
    # If empty -> simulator mode (random jitter values, no real printer)
    moonraker_host: str = ""            # e.g. "192.168.1.42"
    moonraker_port: int = 80
    moonraker_poll_interval: float = 2.0  # seconds
    moonraker_print_grace_s: float = 10.0

    # API
    api_prefix: str = "/api"
    cors_origins: str = "*"
    ui_language: str = "en"
    ui_theme: str = "dark"
    settings_admin_token: str = ""

    # Simulator
    simulator_enabled: bool = True  # automatically enabled when moonraker_host is empty
    simulator_flow_gps: float = 4.0   # grams-per-second reference

    # OCR + optional cloud normalization
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    ocr_enable_cloud_fallback: bool = True
    ocr_openai_model: str = "gpt-4o-mini"
    ocr_anthropic_model: str = "claude-3-5-haiku-latest"
    ocr_cloud_timeout_s: float = 12.0
    ocr_llm_max_chars: int = 4000
    ocr_tesseract_lang: str = "eng+deu"
    ocr_raw_text_limit: int = 5000
    ocr_max_upload_mb: int = 8

    model_config = SettingsConfigDict(env_file=".env", env_prefix="CFS_")


settings = Settings()
