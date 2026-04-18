"""Runtime configuration — read from environment variables."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Database
    database_url: str = "sqlite:///./data/cfs.db"

    # CFS / Moonraker bridge
    # Wenn leer → Simulator-Mode (zufällige Jitter-Werte, kein echter Drucker)
    moonraker_host: str = ""            # z.B. "192.168.1.42"
    moonraker_port: int = 80
    moonraker_poll_interval: float = 2.0  # Sekunden

    # API
    api_prefix: str = "/api"
    cors_origins: str = "*"

    # Simulator
    simulator_enabled: bool = True  # wenn moonraker_host leer → automatisch an
    simulator_flow_gps: float = 4.0   # Gramm pro Sekunde Referenz

    model_config = SettingsConfigDict(env_file=".env", env_prefix="CFS_")


settings = Settings()
