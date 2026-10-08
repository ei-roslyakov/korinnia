"""Life events with participants."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import AppError, ConflictError, NotFoundError
from app.core.security import utcnow
from app.models import Event, EventParticipant, EventType, ParticipantRole
from app.schemas.events import EventCreate, EventUpdate, ParticipantIn
from app.services import audit
from app.services.context import Actor
from app.services.genealogy.common import check_persons, check_place, set_date, to_partial
from app.services.genealogy.snapshots import event_snapshot, set_participants
from app.services.genealogy.vitals import VITAL_TYPES, load_vitals


async def get_event(session: AsyncSession, tree_id: uuid.UUID, event_id: uuid.UUID) -> Event:
    event = (
        await session.scalars(
            select(Event)
            .options(selectinload(Event.place), selectinload(Event.participants))
            .where(Event.id == event_id)
            .execution_options(populate_existing=True)
        )
    ).first()
    if event is None or event.tree_id != tree_id or event.deleted_at is not None:
        raise NotFoundError("event_not_found")
    return event


async def _check_participants(
    session: AsyncSession,
    tree_id: uuid.UUID,
    event_type: EventType,
    participants: list[ParticipantIn],
    *,
    event_id: uuid.UUID | None,
) -> None:
    ids = [p.person_id for p in participants]
    if len(set(ids)) != len(ids):
        raise AppError("duplicate_participant")
    await check_persons(session, tree_id, ids)
    if event_type in VITAL_TYPES:
        principals = [p for p in participants if p.role == ParticipantRole.principal]
        if len(principals) != 1:
            raise AppError("vital_needs_one_principal")
        vitals = (await load_vitals(session, tree_id, [principals[0].person_id])).get(
            principals[0].person_id
        )
        existing = (
            (vitals.birth if event_type == EventType.birth else vitals.death) if vitals else None
        )
        if existing is not None and existing.id != event_id:
            raise ConflictError("vital_exists")


async def create_event(
    session: AsyncSession,
    tree_id: uuid.UUID,
    body: EventCreate,
    actor: Actor,
    *,
    commit: bool = True,
) -> Event:
    await _check_participants(session, tree_id, body.type, body.participants, event_id=None)
    await check_place(session, tree_id, body.place_id)
    user_id = actor.user.id if actor.user else None
    event = Event(
        id=uuid.uuid4(),
        tree_id=tree_id,
        type=body.type,
        title=body.title,
        description=body.description,
        place_id=body.place_id,
        cemetery_name=body.cemetery_name,
        burial_plot=body.burial_plot,
        latitude=body.latitude,
        longitude=body.longitude,
        created_by_id=user_id,
        updated_by_id=user_id,
    )
    set_date(event, "date", "date_sort", to_partial(body.date))
    event.participants = [
        EventParticipant(person_id=p.person_id, role=p.role) for p in body.participants
    ]
    session.add(event)
    await session.flush()
    audit.record(
        session,
        actor,
        "event.create",
        "event",
        event.id,
        tree_id=tree_id,
        after=event_snapshot(event),
    )
    if commit:
        await session.commit()
    return await get_event(session, tree_id, event.id)


async def update_event(
    session: AsyncSession, event: Event, body: EventUpdate, actor: Actor
) -> Event:
    before = event_snapshot(event)
    fields = body.model_fields_set
    new_type = body.type or event.type
    participants = body.participants or [
        ParticipantIn(person_id=p.person_id, role=p.role) for p in event.participants
    ]
    if body.type is not None or body.participants is not None:
        await _check_participants(session, event.tree_id, new_type, participants, event_id=event.id)
    if "place_id" in fields:
        await check_place(session, event.tree_id, body.place_id)
    event.type = new_type
    for f in (
        "title",
        "description",
        "place_id",
        "cemetery_name",
        "burial_plot",
        "latitude",
        "longitude",
    ):
        if f in fields:
            setattr(event, f, getattr(body, f))
    if "date" in fields:
        set_date(event, "date", "date_sort", to_partial(body.date))
    if body.participants is not None:
        set_participants(event, [(p.person_id, p.role) for p in body.participants])
    event.updated_by_id = actor.user.id if actor.user else None
    event.updated_at = utcnow()
    await session.flush()
    after = event_snapshot(event)
    if before != after:
        audit.record(
            session,
            actor,
            "event.update",
            "event",
            event.id,
            tree_id=event.tree_id,
            before=before,
            after=after,
        )
    await session.commit()
    return await get_event(session, event.tree_id, event.id)


async def delete_event(session: AsyncSession, event: Event, actor: Actor) -> None:
    event.deleted_at = utcnow()
    event.deleted_batch_id = event.id
    audit.record(
        session,
        actor,
        "event.delete",
        "event",
        event.id,
        tree_id=event.tree_id,
        before=event_snapshot(event),
    )
    await session.commit()
