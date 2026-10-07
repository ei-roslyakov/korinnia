"""Collaboration: edit suggestions (moderated), comments, open research questions."""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import CommentTarget, QuestionStatus, SuggestionStatus, SuggestionTarget
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, text_enum
from app.models.genealogy_base import TreeScopedMixin


class EditSuggestion(UUIDPrimaryKeyMixin, TreeScopedMixin, TimestampMixin, Base):
    """A contributor's proposed change to a person or event, applied only when an editor
    approves it. `patch` has the shape of the regular update request (PersonUpdate /
    EventUpdate) with only the proposed fields."""

    __tablename__ = "edit_suggestions"
    __table_args__ = (Index("ix_edit_suggestions_target", "entity_type", "entity_id"),)

    entity_type: Mapped[SuggestionTarget] = mapped_column(
        text_enum(SuggestionTarget, "suggestion_target")
    )
    entity_id: Mapped[uuid.UUID] = mapped_column()
    patch: Mapped[dict[str, Any]] = mapped_column(JSONB)
    comment: Mapped[str | None] = mapped_column(Text)
    status: Mapped[SuggestionStatus] = mapped_column(
        text_enum(SuggestionStatus, "suggestion_status"),
        default=SuggestionStatus.pending,
        index=True,
    )
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    reviewed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    reviewed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    review_comment: Mapped[str | None] = mapped_column(Text)


class Comment(UUIDPrimaryKeyMixin, TreeScopedMixin, TimestampMixin, Base):
    __tablename__ = "comments"
    __table_args__ = (Index("ix_comments_target", "entity_type", "entity_id"),)

    entity_type: Mapped[CommentTarget] = mapped_column(text_enum(CommentTarget, "comment_target"))
    entity_id: Mapped[uuid.UUID] = mapped_column()
    body: Mapped[str] = mapped_column(Text)
    author_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    deleted_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))


class OpenQuestion(UUIDPrimaryKeyMixin, TreeScopedMixin, TimestampMixin, Base):
    """An unresolved research question about a person ("Where was he in 1941–1945?")."""

    __tablename__ = "open_questions"

    person_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("persons.id", ondelete="CASCADE"), index=True
    )
    question: Mapped[str] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[QuestionStatus] = mapped_column(
        text_enum(QuestionStatus, "question_status"), default=QuestionStatus.open, index=True
    )
    resolution: Mapped[str | None] = mapped_column(Text)
    resolved_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
