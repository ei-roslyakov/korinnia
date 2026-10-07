"""Application settings, loaded from environment variables (12-factor)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    environment: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    app_version: str = "0.1.0"

    # --- Database -----------------------------------------------------------------
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "korinnia"
    postgres_password: SecretStr = SecretStr("korinnia")
    postgres_db: str = "korinnia"
    # Full URL overrides the individual parts when set.
    database_url_override: str | None = Field(default=None, alias="DATABASE_URL")
    db_pool_size: int = 5
    db_max_overflow: int = 10

    # --- Storage ------------------------------------------------------------------
    # Files live on a local volume (Docker volume / Kubernetes PVC) mounted here.
    media_root: Path = Path("/data/media")

    # --- Security -----------------------------------------------------------------
    secret_key: SecretStr = SecretStr("change-me-in-production")

    # --- Uploads ------------------------------------------------------------------
    max_upload_size_mb: int = 2048

    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url(self) -> str:
        if self.database_url_override:
            return self.database_url_override
        return (
            f"postgresql+psycopg://{self.postgres_user}:"
            f"{self.postgres_password.get_secret_value()}@{self.postgres_host}:"
            f"{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def libpq_conninfo(self) -> str:
        """Plain libpq URL (no SQLAlchemy driver suffix), used by procrastinate."""
        return self.database_url.replace("postgresql+psycopg://", "postgresql://", 1)

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
