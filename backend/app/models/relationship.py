"""Family graph edges: parent→child links and partnerships."""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Index, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.dates import PartialDate
from app.core.enums import ParentChildType, PartnershipEndReason, PartnershipType
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, text_enum
from app.models.genealogy_base import (
    AuthoredMixin,
    SoftDeleteMixin,
    TreeScopedMixin,
    partial_date,
    sort_date_column,
)


class ParentChild(
    UUIDPrimaryKeyMixin, TreeScopedMixin, AuthoredMixin, SoftDeleteMixin, TimestampMixin, Base
):
    __tablename__ = "parent_child"
    __table_args__ = (
        CheckConstraint("parent_id <> child_id", name="not_self"),
        # One live link per parent/child pair (soft-deleted rows don't count).
        Index(
            "uq_parent_child_pair_live",
            "parent_id",
            "child_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    parent_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("persons.id", ondelete="CASCADE"), index=True
    )
    child_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("persons.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[ParentChildType] = mapped_column(
        text_enum(ParentChildType, "parent_child_type"), default=ParentChildType.biological
    )
    notes: Mapped[str | None] = mapped_column(Text)


class Partnership(
    UUIDPrimaryKeyMixin, TreeScopedMixin, AuthoredMixin, SoftDeleteMixin, TimestampMixin, Base
):
    __tablename__ = "partnerships"
    __table_args__ = (CheckConstraint("person_a_id <> person_b_id", name="not_self"),)

    person_a_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("persons.id", ondelete="CASCADE"), index=True
    )
    person_b_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("persons.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[PartnershipType] = mapped_column(
        text_enum(PartnershipType, "partnership_type"), default=PartnershipType.marriage
    )
    start_date: Mapped[PartialDate] = partial_date("start")
    start_sort: Mapped[dt.date | None] = sort_date_column("start")
    end_date: Mapped[PartialDate] = partial_date("end")
    end_sort: Mapped[dt.date | None] = sort_date_column("end")
    end_reason: Mapped[PartnershipEndReason | None] = mapped_column(
        text_enum(PartnershipEndReason, "end_reason")
    )
    place_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("places.id", ondelete="SET NULL"), index=True
    )
    notes: Mapped[str | None] = mapped_column(Text)
