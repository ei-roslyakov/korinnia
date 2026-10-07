"""Birth and death: stored as Events with one principal participant, exposed as fields."""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dates import PartialDate
from app.core.security import utcnow
from app.models import Event, EventParticipant, EventType, ParticipantRole, Person, Place
from app.services.genealogy.common import check_place, set_date

VITAL_TYPES = (EventType.birth, EventType.death)


@dataclass(slots=True)
class Vitals:
    birth: Event | None = None
    death: Event | None = None

    @property
    def birth_date(self) -> PartialDate | None:
        return self.birth.date if self.birth else None

    @property
    def death_date(self) -> PartialDate | None:
        return self.death.date if self.death else None


async def load_vitals(
    session: AsyncSession, tree_id: uuid.UUID, person_ids: Iterable[uuid.UUID] | None = None
) -> dict[uuid.UUID, Vitals]:
    """Birth/death events per person. `person_ids=None` loads the whole tree."""
    stmt = (
        select(EventParticipant.person_id, Event)
        .join(Event, Event.id == EventParticipant.event_id)
        .options(selectinload(Event.place))
        .where(
            Event.tree_id == tree_id,
            Event.deleted_at.is_(None),
            Event.type.in_(VITAL_TYPES),
            EventParticipant.role == ParticipantRole.principal,
        )
    )
    if person_ids is not None:
        ids = list(person_ids)
        if not ids:
            return {}
        stmt = stmt.where(EventParticipant.person_id.in_(ids))
    result: dict[uuid.UUID, Vitals] = {}
    for person_id, event in (await session.execute(stmt)).all():
        v = result.setdefault(person_id, Vitals())
        if event.type == EventType.birth:
            v.birth = event
        else:
            v.death = event
    return result


async def vitals_of(session: AsyncSession, person: Person) -> Vitals:
    return (await load_vitals(session, person.tree_id, [person.id])).get(person.id, Vitals())


async def set_vital(
    session: AsyncSession,
    person: Person,
    event_type: EventType,
    *,
    date: PartialDate | None,
    place_id: uuid.UUID | None,
    description: str | None,
    remove: bool,
    user_id: uuid.UUID | None,
) -> Event | None:
    """Create, update or (soft-)delete the person's birth/death event."""
    vitals = await vitals_of(session, person)
    existing = vitals.birth if event_type == EventType.birth else vitals.death
    if remove:
        if existing is not None:
            existing.deleted_at = utcnow()
            existing.deleted_batch_id = existing.id
        return None
    place: Place | None = await check_place(session, person.tree_id, place_id)
    event = existing
    if event is None:
        event = Event(
            id=uuid.uuid4(),
            tree_id=person.tree_id,
            type=event_type,
            created_by_id=user_id,
        )
        event.participants = [EventParticipant(person_id=person.id, role=ParticipantRole.principal)]
        session.add(event)
    set_date(event, "date", "date_sort", date or PartialDate())
    event.place_id = place.id if place else None
    event.description = description
    event.updated_by_id = user_id
    return event
