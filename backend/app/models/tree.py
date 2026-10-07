"""Family trees and per-tree membership (roles)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import TreeRole
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, text_enum
from app.models.user import User


class Tree(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "trees"
    __table_args__ = (
        # At most one live demo copy per owner (guards against concurrent creation).
        Index(
            "uq_trees_demo_owner",
            "owner_id",
            unique=True,
            postgresql_where=text("is_demo AND deleted_at IS NULL"),
        ),
    )

    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # The fictional demo family (each user gets their own copy to explore and practise on).
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    owner: Mapped[User | None] = relationship()
    memberships: Mapped[list[TreeMembership]] = relationship(
        back_populates="tree", cascade="all, delete-orphan", passive_deletes=True
    )


class TreeMembership(TimestampMixin, Base):
    __tablename__ = "tree_memberships"

    tree_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("trees.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    role: Mapped[TreeRole] = mapped_column(text_enum(TreeRole, "tree_role"))

    tree: Mapped[Tree] = relationship(back_populates="memberships")
    user: Mapped[User] = relationship()
