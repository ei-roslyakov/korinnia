"""Application settings, loaded from environment variables (12-factor)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import quote

from pydantic import Field, SecretStr, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.enums import Language


class Settings(BaseSettings):
    # ../.env lets backend tools run from backend/ on the host with the repo-root .env.
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"), extra="ignore", case_sensitive=False
    )

    environment: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    # Release version, baked into the image by the Deploy workflow ("dev" for local builds).
    app_version: str = "dev"

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
    # Public URL of the app, used to build invitation / password-reset links.
    public_base_url: str = "http://localhost:8080"
    # Secure cookies need HTTPS (set false only for plain-HTTP local development).
    cookie_secure: bool = True
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 30
    mfa_token_ttl_minutes: int = 5
    invitation_ttl_hours: int = 7 * 24
    password_reset_ttl_hours: int = 24
    password_min_length: int = 10
    # Login throttling: max failed attempts in the window, per email and per client IP.
    login_window_minutes: int = 15
    login_max_failures_per_email: int = 5
    login_max_failures_per_ip: int = 20

    # --- Bootstrap ----------------------------------------------------------------
    superadmin_email: str | None = None
    superadmin_password: SecretStr | None = None

    # --- Language -----------------------------------------------------------------
    # Interface language for visitors who have not chosen one, and for new accounts.
    default_language: Language = Language.en

    # --- Demo ---------------------------------------------------------------------
    # Give every new account its own copy of the fictional demo family to explore.
    demo_tree_for_new_users: bool = True

    # --- Uploads / media ----------------------------------------------------------
    max_upload_size_mb: int = 2048
    # Hand file downloads to nginx (X-Accel-Redirect to its internal /_media/ location) for
    # requests that came through nginx (it sets X-Media-Accel); others are streamed directly.
    # Disable when the backend is reached without nginx (tests, direct dev access).
    media_x_accel: bool = True

    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url(self) -> str:
        if self.database_url_override:
            return self.database_url_override
        # Percent-encode credentials: generated passwords may contain URL characters (@ # / :).
        user = quote(self.postgres_user, safe="")
        password = quote(self.postgres_password.get_secret_value(), safe="")
        return (
            f"postgresql+psycopg://{user}:{password}@{self.postgres_host}:"
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
