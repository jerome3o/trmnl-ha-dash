"""Application configuration."""

import os
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Home Assistant
    ha_url: str = os.getenv("HA_URL", "http://homeassistant.local:8123")
    ha_api_key: str = os.getenv("HA_API_KEY", "")

    # Server
    server_host: str = os.getenv("SERVER_HOST", "0.0.0.0")
    server_port: int = int(os.getenv("SERVER_PORT", "8000"))

    # Dashboard
    dashboard_refresh_interval: int = int(
        os.getenv("DASHBOARD_REFRESH_INTERVAL", "900")
    )  # 15 minutes (how often TRMNL polls)

    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    class Config:
        """Pydantic config."""

        env_file = ".env"
        case_sensitive = False


settings = Settings()
