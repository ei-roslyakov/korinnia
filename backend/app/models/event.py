"""Life events (birth, death, marriage, emigration, ...) and their participants."""

from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.dates import PartialDate
from app.core.enums import EventType, ParticipantRole
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, text_enum
from app.models.genealogy_base import (
    AuthoredMixin,
    SoftDeleteMixin,
    TreeScopedMixin,
    partial_date,
    sort_date_column,
)
from app.models.person import Person
from app.models.place import Place


class Event(
    UUIDPrimaryKeyMixin, TreeScopedMixin, AuthoredMixin, SoftDeleteMixin, TimestampMixin, Base
):
    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint("latitude BETWEEN -90 AND 90", name="latitude_range"),
        CheckConstraint("longitude BETWEEN -180 AND 180", name="longitude_range"),
    )

    type: Mapped[EventType] = mapped_column(text_enum(EventType, "event_type"), index=True)
    title: Mapped[str | None] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)  # Markdown
    date: Mapped[PartialDate] = partial_date("date")
    date_sort: Mapped[dt.date | None] = sort_date_column("date")
    place_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("places.id", ondelete="SET NULL"), index=True
    )
    # Burial details (also usable for other events at a precise spot).
    cemetery_name: Mapped[str | None] = mapped_column(String(300))
    burial_plot: Mapped[str | None] = mapped_column(String(200))
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))

    place: Mapped[Place | None] = relationship()
    participants: Mapped[list[EventParticipant]] = relationship(
        back_populates="event", cascade="all, delete-orphan", passive_deletes=True
    )


class EventParticipant(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "event_participants"
    __table_args__ = (UniqueConstraint("event_id", "person_id"),)

    event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), index=True
    )
    person_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("persons.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[ParticipantRole] = mapped_column(
        text_enum(ParticipantRole, "participant_role"), default=ParticipantRole.principal
    )

    event: Mapped[Event] = relationship(back_populates="participants")
    person: Mapped[Person] = relationship()
