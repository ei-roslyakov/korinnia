"""Users and their authentication artefacts."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import Language
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, text_enum, utcnow_column


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (Index("uq_users_email_lower", text("lower(email)"), unique=True),)

    email: Mapped[str] = mapped_column(String(320))
    password_hash: Mapped[str | None] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(200))
    preferred_language: Mapped[Language] = mapped_column(
        text_enum(Language, "user_language"), default=Language.uk, server_default=Language.uk
    )
    is_superadmin: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Tokens issued before this moment are rejected (password change, deactivation, "log out
    # everywhere"). Stored with second precision to match JWT `iat`.
    sessions_valid_after: Mapped[datetime] = utcnow_column()

    # TOTP two-factor authentication
    totp_secret: Mapped[str | None] = mapped_column(String(64))
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    # Last accepted TOTP time-step: prevents replaying a code within its validity window.
    totp_last_counter: Mapped[int | None] = mapped_column(Integer)

    recovery_codes: Mapped[list[RecoveryCode]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )


class RecoveryCode(UUIDPrimaryKeyMixin, Base):
    """One-time 2FA recovery codes (stored as SHA-256; the codes themselves are random)."""

    __tablename__ = "recovery_codes"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    code_hash: Mapped[str] = mapped_column(String(64))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = utcnow_column()

    user: Mapped[User] = relationship(back_populates="recovery_codes")


class RefreshToken(Base):
    """Server-side record of each issued refresh token (enables rotation, reuse detection,
    and revocation). `id` is the JWT `jti`; tokens of one login share a `family_id`."""

    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    family_id: Mapped[uuid.UUID] = mapped_column(index=True)
    created_at: Mapped[datetime] = utcnow_column()
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    replaced_by_id: Mapped[uuid.UUID | None] = mapped_column()
    user_agent: Mapped[str | None] = mapped_column(String(500))
    ip_address: Mapped[str | None] = mapped_column(String(64))


class LoginAttempt(UUIDPrimaryKeyMixin, Base):
    """Login attempts, used for throttling (Postgres instead of Redis)."""

    __tablename__ = "login_attempts"
    __table_args__ = (
        Index("ix_login_attempts_email_created", "email", "created_at"),
        Index("ix_login_attempts_ip_created", "ip_address", "created_at"),
    )

    email: Mapped[str] = mapped_column(String(320))
    ip_address: Mapped[str | None] = mapped_column(String(64))
    success: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = utcnow_column()
