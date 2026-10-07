"""Soft delete, trash bin and restore; restoring earlier revisions from the audit log.

Deleting a person also soft-deletes their relationships and the events only they take
part in. All rows deleted together share `deleted_batch_id` = id of the entity the user
deleted (the batch "root"), so a restore brings the whole batch back. Nothing is ever
removed from the database by these operations.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import AppError, ConflictError, NotFoundError
from app.core.security import utcnow
from app.models import (
    AuditLog,
    Citation,
    Event,
    EventParticipant,
    MediaFile,
    MediaKind,
    MediaPerson,
    ParentChild,
    Partnership,
    Person,
    Place,
    Source,
    Story,
)
from app.schemas.history import TrashEntityType, TrashItem
from app.schemas.persons import DeletePreview
from app.services import audit
from app.services.context import Actor
from app.services.genealogy import sources as sources_service
from app.services.genealogy import stories as stories_service
from app.services.genealogy.common import date_from_dict, name_display, pick_primary, set_date
from app.services.genealogy.media import snapshot as media_snapshot
from app.services.genealogy.persons import snapshot_of
from app.services.genealogy.snapshots import (
    apply_event_snapshot,
    apply_parent_child_snapshot,
    apply_partnership_snapshot,
    apply_person_snapshot,
    apply_place_snapshot,
    event_snapshot,
    parent_child_snapshot,
    partnership_snapshot,
    place_snapshot,
)
from app.services.genealogy.summaries import load_names, summaries_for

MODELS: dict[str, type[Any]] = {
    "person": Person,
    "place": Place,
    "event": Event,
    "parent_child": ParentChild,
    "partnership": Partnership,
    "media": MediaFile,
    "source": Source,
    "citation": Citation,
    "story": Story,
}
GENEALOGY_ENTITY_TYPES = tuple(MODELS)


async def _sole_participant_events(session: AsyncSession, person_id: uuid.UUID) -> list[uuid.UUID]:
    """Live events in which this person is the only participant."""
    counts = (
        select(EventParticipant.event_id, func.count().label("n"))
        .group_by(EventParticipant.event_id)
        .subquery()
    )
    rows = await session.scalars(
        select(Event.id)
        .join(EventParticipant, EventParticipant.event_id == Event.id)
        .join(counts, counts.c.event_id == Event.id)
        .where(
            EventParticipant.person_id == person_id,
            Event.deleted_at.is_(None),
            counts.c.n == 1,
        )
    )
    return list(rows)


def _person_links(person_id: uuid.UUID) -> tuple[Any, Any]:
    return (
        or_(ParentChild.parent_id == person_id, ParentChild.child_id == person_id),
        or_(Partnership.person_a_id == person_id, Partnership.person_b_id == person_id),
    )


async def delete_preview(session: AsyncSession, person: Person) -> DeletePreview:
    pc_filter, pa_filter = _person_links(person.id)
    links = list(
        await session.scalars(
            select(ParentChild).where(pc_filter, ParentChild.deleted_at.is_(None))
        )
    )
    partnerships = await session.scalar(
        select(func.count()).where(pa_filter, Partnership.deleted_at.is_(None))
    )
    own_events = await _sole_participant_events(session, person.id)
    all_events = await session.scalar(
        select(func.count())
        .select_from(Event)
        .join(EventParticipant, EventParticipant.event_id == Event.id)
        .where(EventParticipant.person_id == person.id, Event.deleted_at.is_(None))
    )
    summary = (await summaries_for(session, person.tree_id, [person]))[0]
    return DeletePreview(
        person=summary,
        parent_links=sum(1 for link in links if link.child_id == person.id),
        child_links=sum(1 for link in links if link.parent_id == person.id),
        partnerships=partnerships or 0,
        events=len(own_events),
        shared_events=(all_events or 0) - len(own_events),
    )


async def delete_person(session: AsyncSession, person: Person, actor: Actor) -> None:
    before = await snapshot_of(session, person)
    now, batch = utcnow(), person.id
    pc_filter, pa_filter = _person_links(person.id)
    marks = {"deleted_at": now, "deleted_batch_id": batch}
    await session.execute(
        update(ParentChild).where(pc_filter, ParentChild.deleted_at.is_(None)).values(**marks)
    )
    await session.execute(
        update(Partnership).where(pa_filter, Partnership.deleted_at.is_(None)).values(**marks)
    )
    own_events = await _sole_participant_events(session, person.id)
    if own_events:
        await session.execute(update(Event).where(Event.id.in_(own_events)).values(**marks))
    person.deleted_at = now
    person.deleted_batch_id = batch
    audit.record(
        session, actor, "person.delete", "person", person.id, tree_id=person.tree_id, before=before
    )
    await session.commit()


# --- Trash ------------------------------------------------------------------------------


async def _label(session: AsyncSession, entity_type: str, obj: Any) -> str:
    if isinstance(obj, Person):
        names = (await load_names(session, [obj.id], obj.tree_id)).get(obj.id, [])
        return name_display(pick_primary(names))
    if isinstance(obj, Place):
        return str(obj.name)
    if isinstance(obj, MediaFile):
        return str(obj.title or obj.original_filename)
    if isinstance(obj, Source | Story):
        return str(obj.title)
    if isinstance(obj, Citation):
        source = await session.get(Source, obj.source_id)
        return f"{source.title if source else '?'}{f', {obj.page}' if obj.page else ''}"
    if isinstance(obj, Event):
        return f"{obj.type.value} {obj.date.to_text()}".strip()
    if isinstance(obj, ParentChild):
        parent = await _person_label(session, obj.parent_id)
        child = await _person_label(session, obj.child_id)
        return f"{parent} → {child}"
    if isinstance(obj, Partnership):
        a = await _person_label(session, obj.person_a_id)
        b = await _person_label(session, obj.person_b_id)
        return f"{a} ⚭ {b}"
    return entity_type  # pragma: no cover


async def _person_label(session: AsyncSession, person_id: uuid.UUID) -> str:
    person = await session.get(Person, person_id)
    if person is None:  # pragma: no cover - FK guarantees existence
        return "?"
    names = (await load_names(session, [person_id], person.tree_id)).get(person_id, [])
    return name_display(pick_primary(names))


async def list_trash(session: AsyncSession, tree_id: uuid.UUID) -> list[TrashItem]:
    items: list[TrashItem] = []
    for entity_type, model in MODELS.items():
        roots = await session.scalars(
            select(model).where(
                model.tree_id == tree_id,
                model.deleted_at.is_not(None),
                model.deleted_batch_id == model.id,
            )
        )
        for obj in roots:
            batch_size = 0
            for m in MODELS.values():
                batch_size += (
                    await session.scalar(
                        select(func.count()).select_from(m).where(m.deleted_batch_id == obj.id)
                    )
                    or 0
                )
            deleted_by = await session.scalar(
                select(AuditLog.user_label)
                .where(
                    AuditLog.entity_id == obj.id,
                    AuditLog.action == f"{entity_type}.delete",
                )
                .order_by(AuditLog.created_at.desc())
                .limit(1)
            )
            items.append(
                TrashItem(
                    entity_type=entity_type,
                    entity_id=obj.id,
                    label=await _label(session, entity_type, obj),
                    deleted_at=obj.deleted_at,
                    deleted_by=deleted_by,
                    batch_size=batch_size,
                )
            )
    items.sort(key=lambda i: i.deleted_at, reverse=True)
    return items


async def restore_from_trash(
    session: AsyncSession,
    tree_id: uuid.UUID,
    entity_type: TrashEntityType,
    entity_id: uuid.UUID,
    actor: Actor,
) -> None:
    model = MODELS[entity_type]
    root = await session.get(model, entity_id)
    if (
        root is None
        or root.tree_id != tree_id
        or root.deleted_at is None
        or root.deleted_batch_id != root.id
    ):
        raise NotFoundError("not_in_trash")
    batch = root.id
    restore = {"deleted_at": None, "deleted_batch_id": None}
    # Relationship rows whose live duplicate was created meanwhile stay in the trash.
    live_pairs = (
        select(ParentChild.parent_id, ParentChild.child_id)
        .where(ParentChild.deleted_at.is_(None))
        .subquery()
    )
    duplicate_ids = select(ParentChild.id).join(
        live_pairs,
        (live_pairs.c.parent_id == ParentChild.parent_id)
        & (live_pairs.c.child_id == ParentChild.child_id),
    )
    for m in MODELS.values():
        stmt = update(m).where(m.deleted_batch_id == batch).values(**restore)
        if m is ParentChild:
            stmt = stmt.where(ParentChild.id.notin_(duplicate_ids))
        await session.execute(stmt)
    await session.refresh(root)
    audit.record(
        session,
        actor,
        f"{entity_type}.restore",
        entity_type,
        root.id,
        tree_id=tree_id,
        after=await _snapshot(session, entity_type, root),
    )
    await session.commit()


# --- Revisions --------------------------------------------------------------------------


async def _snapshot(session: AsyncSession, entity_type: str, obj: Any) -> dict[str, Any]:
    match entity_type:
        case "person":
            return await snapshot_of(session, obj)
        case "event":
            await session.refresh(obj, ["participants"])
            return event_snapshot(obj)
        case "parent_child":
            return parent_child_snapshot(obj)
        case "partnership":
            return partnership_snapshot(obj)
        case "media":
            return media_snapshot(obj, await _media_tags(session, obj.id))
        case "source":
            return sources_service.source_snapshot(
                obj, await sources_service.source_media_ids(session, obj.id)
            )
        case "citation":
            return sources_service.citation_snapshot(obj)
        case "story":
            return await stories_service.snapshot_of(session, obj)
        case _:
            return place_snapshot(obj)


async def restore_revision(
    session: AsyncSession, tree_id: uuid.UUID, entry_id: uuid.UUID, actor: Actor
) -> tuple[str, uuid.UUID]:
    """Make an entity look exactly as it did right after the given change."""
    entry = await session.get(AuditLog, entry_id)
    if (
        entry is None
        or entry.tree_id != tree_id
        or entry.entity_type not in MODELS
        or entry.entity_id is None
    ):
        raise NotFoundError("revision_not_found")
    if entry.after is None:
        raise AppError("revision_not_restorable")
    model = MODELS[entry.entity_type]
    options = [selectinload(Event.participants)] if model is Event else []
    obj = await session.get(model, entry.entity_id, options=options)
    if obj is None:  # pragma: no cover - rows are never hard-deleted
        raise NotFoundError("revision_not_found")
    if obj.deleted_at is not None:
        raise ConflictError("entity_deleted")
    before = await _snapshot(session, entry.entity_type, obj)
    user_id = actor.user.id if actor.user else None
    snap = entry.after
    match entry.entity_type:
        case "person":
            await apply_person_snapshot(session, obj, snap, user_id)
        case "event":
            apply_event_snapshot(obj, snap, user_id)
        case "parent_child":
            apply_parent_child_snapshot(obj, snap)
        case "partnership":
            apply_partnership_snapshot(obj, snap)
        case "place":
            apply_place_snapshot(obj, snap)
        case "media":
            await _apply_media_snapshot(session, obj, snap)
        case "source":
            await sources_service.apply_source_snapshot(session, obj, snap)
        case "citation":
            sources_service.apply_citation_snapshot(obj, snap)
        case "story":
            await stories_service.apply_snapshot(session, obj, snap)
    obj.updated_at = utcnow()
    await session.flush()
    after = await _snapshot(session, entry.entity_type, obj)
    audit.record(
        session,
        actor,
        f"{entry.entity_type}.restore_revision",
        entry.entity_type,
        obj.id,
        tree_id=tree_id,
        before=before,
        after=after,
    )
    await session.commit()
    return entry.entity_type, obj.id


async def _media_tags(session: AsyncSession, media_id: uuid.UUID) -> list[MediaPerson]:
    return list(await session.scalars(select(MediaPerson).where(MediaPerson.media_id == media_id)))


async def _apply_media_snapshot(
    session: AsyncSession, media: MediaFile, snap: dict[str, Any]
) -> None:
    media.kind = MediaKind(snap["kind"])
    media.title = snap.get("title")
    media.description = snap.get("description")
    set_date(media, "date", "date_sort", date_from_dict(snap.get("date")))
    media.place_id = uuid.UUID(snap["place_id"]) if snap.get("place_id") else None
    wanted = {uuid.UUID(p["person_id"]): p.get("region") for p in snap.get("people", [])}
    for tag in await _media_tags(session, media.id):
        if tag.person_id in wanted:
            tag.region = wanted.pop(tag.person_id)
        else:
            await session.delete(tag)
    for person_id, region in wanted.items():
        session.add(MediaPerson(media_id=media.id, person_id=person_id, region=region))
