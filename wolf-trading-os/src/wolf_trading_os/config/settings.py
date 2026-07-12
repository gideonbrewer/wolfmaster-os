"""Application settings loaded from environment variables / .env.

Credentials are never stored in source code; everything sensitive comes
from the environment. See `.env.example` at the project root.
"""

from __future__ import annotations

import enum
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(enum.StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="WTOS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Environment = Environment.DEVELOPMENT
    database_url: str = "postgresql+psycopg://wolf:wolf@localhost:5432/wolf_trading_os"
    log_format: str = "json"  # "json" | "console"
    log_level: str = "INFO"

    @property
    def is_development(self) -> bool:
        return self.environment is Environment.DEVELOPMENT


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings instance."""
    return Settings()
