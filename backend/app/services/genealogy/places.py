from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError
from app.core.security import utcnow
from app.models import Event, Partnership, Place
from app.schemas.places import PlaceCreate, PlaceUpdate
from app.services import audit
from app.services.context import Actor
from app.services.genealogy.common import get_live
from app.services.genealogy.snapshots import place_search_text, place_snapshot
from app.services.search_text import query_alternatives


async def search_places(
    session: AsyncSession, tree_id: uuid.UUID, q: str | None, *, limit: int, offset: int
) -> tuple[list[Place], int]:
    stmt = select(Place).where(Place.tree_id == tree_id, Place.deleted_at.is_(None))
    for alts in query_alternatives(q or ""):
        stmt = stmt.where(or_(*(Place.search_text.ilike(f"%{a}%") for a in alts)))
    total = await session.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = await session.scalars(
        stmt.order_by(func.lower(Place.name), Place.id).limit(limit).offset(offset)
    )
    return list(rows), total or 0


async def get_place(session: AsyncSession, tree_id: uuid.UUID, place_id: uuid.UUID) -> Place:
    return await get_live(session, Place, tree_id, place_id, "place_not_found")


def _apply(place: Place, data: dict[str, Any]) -> None:
    for key, value in data.items():
        if key == "historical_names":
            value = [dict(h) for h in value] if value is not None else []
        setattr(place, key, value)
    place.search_text = place_search_text(place)


async def create_place(
    session: AsyncSession,
    tree_id: uuid.UUID,
    body: PlaceCreate,
    actor: Actor,
    *,
    commit: bool = True,
) -> Place:
    place = Place(id=uuid.uuid4(), tree_id=tree_id, created_by_id=actor.user and actor.user.id)
    _apply(
        place,
        body.model_dump(mode="json") | {"latitude": body.latitude, "longitude": body.longitude},
    )
    session.add(place)
    await session.flush()
    audit.record(
        session,
        actor,
        "place.create",
        "place",
        place.id,
        tree_id=tree_id,
        after=place_snapshot(place),
    )
    if commit:
        await session.commit()
    return place


async def update_place(
    session: AsyncSession, place: Place, body: PlaceUpdate, actor: Actor
) -> Place:
    before = place_snapshot(place)
    data = body.model_dump(exclude_unset=True, mode="json")
    for coord in ("latitude", "longitude"):
        if coord in data:
            data[coord] = getattr(body, coord)
    _apply(place, data)
    place.updated_by_id = actor.user.id if actor.user else None
    after = place_snapshot(place)
    if before != after:
        audit.record(
            session,
            actor,
            "place.update",
            "place",
            place.id,
            tree_id=place.tree_id,
            before=before,
            after=after,
        )
    await session.commit()
    await session.refresh(place)
    return place


async def delete_place(session: AsyncSession, place: Place, actor: Actor) -> None:
    used = (
        await session.scalar(
            select(func.count())
            .select_from(Event)
            .where(Event.place_id == place.id, Event.deleted_at.is_(None))
        )
        or 0
    )
    used += (
        await session.scalar(
            select(func.count())
            .select_from(Partnership)
            .where(and_(Partnership.place_id == place.id, Partnership.deleted_at.is_(None)))
        )
        or 0
    )
    if used:
        raise ConflictError("place_in_use", extra={"usages": used})
    place.deleted_at = utcnow()
    place.deleted_batch_id = place.id
    audit.record(
        session,
        actor,
        "place.delete",
        "place",
        place.id,
        tree_id=place.tree_id,
        before=place_snapshot(place),
    )
    await session.commit()
