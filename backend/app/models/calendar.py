"""Calendar feeds: a member's private iCalendar subscription to a tree's anniversaries."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import Language
from app.models.base import Base, UUIDPrimaryKeyMixin, text_enum, utcnow_column


class CalendarFeed(UUIDPrimaryKeyMixin, Base):
    """One per member and tree. Calendar apps cannot sign in, so the URL carries a secret
    token; only its SHA-256 is stored (D115). Revoking deletes the row."""

    __tablename__ = "calendar_feeds"
    __table_args__ = (UniqueConstraint("tree_id", "user_id"),)

    tree_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("trees.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    # Language of the event titles in the feed.
    language: Mapped[Language] = mapped_column(text_enum(Language, "feed_language"))
    created_at: Mapped[datetime] = utcnow_column()
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Rate limit: fetches counted in the current hour.
    window_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    window_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
