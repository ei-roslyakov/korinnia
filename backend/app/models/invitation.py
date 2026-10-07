"""One-time links: invitations for new users and admin-initiated password resets.

Only a SHA-256 of the token is stored; the token itself exists only in the link.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import TreeRole
from app.models.base import Base, UUIDPrimaryKeyMixin, text_enum, utcnow_column
from app.models.tree import Tree
from app.models.user import User


class Invitation(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "invitations"

    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    email: Mapped[str] = mapped_column(String(320), index=True)
    tree_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("trees.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[TreeRole | None] = mapped_column(text_enum(TreeRole, "invitation_role"))
    is_superadmin: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = utcnow_column()
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accepted_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    tree: Mapped[Tree | None] = relationship()
    created_by: Mapped[User | None] = relationship(foreign_keys=[created_by_id])


class PasswordResetToken(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "password_reset_tokens"

    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = utcnow_column()
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(foreign_keys=[user_id])
