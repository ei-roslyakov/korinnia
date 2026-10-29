"""Stories and memories, linked to people and media."""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.dates import PartialDate
from app.core.enums import StoryKind, StoryStatus
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, text_enum
from app.models.genealogy_base import (
    AuthoredMixin,
    SoftDeleteMixin,
    TreeScopedMixin,
    partial_date,
    sort_date_column,
)


class Story(
    UUIDPrimaryKeyMixin, TreeScopedMixin, AuthoredMixin, SoftDeleteMixin, TimestampMixin, Base
):
    __tablename__ = "stories"

    title: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text, default="")  # Markdown
    # Who told it, free text: "told by grandmother Halyna in 2019".
    narrator: Mapped[str | None] = mapped_column(String(300))
    # When the story happened (not when it was written).
    date: Mapped[PartialDate] = partial_date("date")
    date_sort: Mapped[dt.date | None] = sort_date_column("date")
    status: Mapped[StoryStatus] = mapped_column(
        text_enum(StoryStatus, "story_status"), default=StoryStatus.draft, index=True
    )
    # The account that wrote it (created_by_id may differ for imported stories).
    author_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    review_comment: Mapped[str | None] = mapped_column(Text)
    # A family recipe or tradition is a story too (D117): same narrator, people, media,
    # review and comments, plus the recipe's structured parts and the occasion.
    kind: Mapped[StoryKind] = mapped_column(
        text_enum(StoryKind, "story_kind"),
        default=StoryKind.story,
        server_default=StoryKind.story,
        index=True,
    )
    # {servings, prep_minutes, cook_minutes, ingredients: [{amount, item}], steps: [str]}
    recipe: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    # "Christmas Eve", "Easter", "Wedding"…
    occasion: Mapped[str | None] = mapped_column(String(200))


class StoryPerson(Base):
    __tablename__ = "story_persons"

    story_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stories.id", ondelete="CASCADE"), primary_key=True
    )
    person_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("persons.id", ondelete="CASCADE"), primary_key=True, index=True
    )


class StoryMedia(Base):
    __tablename__ = "story_media"

    story_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stories.id", ondelete="CASCADE"), primary_key=True
    )
    media_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("media_files.id", ondelete="CASCADE"), primary_key=True
    )
