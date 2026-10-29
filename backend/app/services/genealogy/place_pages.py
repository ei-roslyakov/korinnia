"""Place pages (D116): the list of places with how much happened there, one place's page,
and merging a duplicate place into another one."""

from __future__ import annotations

import math
import uuid
from collections import Counter
from collections.abc import Sequence
from typing import Any

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.security import utcnow
from app.models import AuditLog, Event, MediaFile, Partnership, Place, TreeRole, User
from app.schemas.place_pages import NearbyPlace, PlaceIndexItem, PlaceMergeIn, PlacePage
from app.schemas.places import PlaceOut, PlaceSummary
from app.services import audit
from app.services.context import Actor
from app.services.genealogy import media as media_service
from app.services.genealogy import stories as story_service
from app.services.genealogy.facts import FactRow, in_date_order, load_facts
from app.services.genealogy.places import get_place
from app.services.genealogy.snapshots import place_search_text, place_snapshot
from app.services.genealogy.summaries import summary_map
from app.services.search_text import query_alternatives
from app.services.visibility import Visibility

NEARBY_KM = 25
NEARBY_LIMIT = 10
EARTH_RADIUS_KM = 6371.0


def distance_km(a: Place | PlaceSummary, b: Place | PlaceSummary) -> float | None:
    """Great-circle distance (haversine); None when either has no coordinates."""
    coords = [a.latitude, a.longitude, b.latitude, b.longitude]
    if any(v is None for v in coords):
        return None
    lat1, lon1, lat2, lon2 = (math.radians(float(v)) for v in coords if v is not None)
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(h))


def _place_id(r: FactRow) -> uuid.UUID | None:
    return r.place.id if r.place else None


def _names(place: Place) -> list[str]:
    return [place.name, *(h["name"] for h in place.historical_names or [] if h.get("name"))]


async def _live_places(session: AsyncSession, tree_id: uuid.UUID) -> list[Place]:
    return list(
        await session.scalars(
            select(Place).where(Place.tree_id == tree_id, Place.deleted_at.is_(None))
        )
    )


# --- List -----------------------------------------------------------------------------------


async def place_index(
    session: AsyncSession, tree_id: uuid.UUID, seen: Visibility, q: str | None = None
) -> list[PlaceIndexItem]:
    """Every place with the number of facts and people there, most first. `q` matches any
    name variant, historical ones included, in either script."""
    stmt = select(Place).where(Place.tree_id == tree_id, Place.deleted_at.is_(None))
    for alts in query_alternatives(q or ""):
        stmt = stmt.where(or_(*(Place.search_text.ilike(f"%{a}%") for a in alts)))
    places = list(await session.scalars(stmt))
    facts = await load_facts(session, tree_id, seen.protected)
    events: Counter[uuid.UUID] = Counter()
    people: dict[uuid.UUID, set[uuid.UUID]] = {}
    for r in facts.rows:
        if (pid := _place_id(r)) is not None:
            events[pid] += 1
            people.setdefault(pid, set()).update(p for p, _ in r.persons)
    items = [
        PlaceIndexItem(
            place=PlaceOut.model_validate(p),
            events=events[p.id],
            people=len(people.get(p.id, ())),
        )
        for p in places
    ]
    items.sort(key=lambda i: (-i.events, i.place.name.lower()))
    return items


# --- One place ------------------------------------------------------------------------------


async def place_page(
    session: AsyncSession,
    tree_id: uuid.UUID,
    place_id: uuid.UUID,
    user: User,
    role: TreeRole,
    seen: Visibility,
) -> PlacePage:
    place = await get_place(session, tree_id, place_id)
    facts = await load_facts(session, tree_id, seen.protected)
    here = in_date_order(r for r in facts.rows if _place_id(r) == place.id)
    person_ids = {pid for r in here for pid, _ in r.persons}
    persons = await summary_map(session, tree_id, person_ids)

    media_rows = list(
        await session.scalars(
            select(MediaFile)
            .where(
                MediaFile.tree_id == tree_id,
                MediaFile.place_id == place.id,
                MediaFile.deleted_at.is_(None),
                MediaFile.id.not_in(seen.hidden_media),
            )
            .order_by(MediaFile.date_sort.asc().nulls_last(), MediaFile.created_at)
        )
    )
    stories, _ = await story_service.list_stories(
        session, tree_id, user, role, limit=50, hidden=seen.protected, mentions=_names(place)
    )

    nearby: list[NearbyPlace] = []
    for other in await _live_places(session, tree_id):
        km = distance_km(place, other) if other.id != place.id else None
        if km is not None and km <= NEARBY_KM:
            nearby.append(NearbyPlace(place=PlaceSummary.model_validate(other), distance_km=km))
    nearby.sort(key=lambda n: n.distance_km)

    return seen.redact(
        PlacePage(
            place=PlaceOut.model_validate(place),
            counts=dict(Counter(r.type for r in here)),
            facts=[facts.out(r) for r in here],
            persons=sorted(persons.values(), key=lambda s: s.display_name.lower()),
            media=await media_service.media_out_many(session, media_rows),
            stories=await story_service.summaries(session, stories, seen),
            nearby=nearby[:NEARBY_LIMIT],
        )
    )


# --- Merging --------------------------------------------------------------------------------

MERGED = "place.merge"


async def _move(
    session: AsyncSession,
    ids: dict[str, list[uuid.UUID]],
    to: uuid.UUID,
    only_from: uuid.UUID | None,
) -> None:
    for key, model in (("events", Event), ("partnerships", Partnership), ("media", MediaFile)):
        if not ids.get(key):
            continue
        stmt = update(model).where(model.id.in_(ids[key]))
        if only_from is not None:
            stmt = stmt.where(model.place_id == only_from)
        await session.execute(stmt.values(place_id=to))
    # Rows already loaded in this session still point at the old place (and its object).
    for obj in list(session.identity_map.values()):
        if isinstance(obj, Event | Partnership | MediaFile):
            session.expire(obj)


def _merged_names(source: Place, target: Place) -> list[dict[str, Any]]:
    """The source's names become historical names of the target (no duplicates)."""
    known = {n.strip().lower() for n in _names(target)}
    added: list[dict[str, Any]] = []
    for h in [{"name": source.name}, *(source.historical_names or [])]:
        name = (h.get("name") or "").strip()
        if name and name.lower() not in known:
            known.add(name.lower())
            added.append({k: v for k, v in h.items() if v is not None} | {"name": name})
    return added


async def merge_place(
    session: AsyncSession, source: Place, body: PlaceMergeIn, actor: Actor
) -> Place:
    """Move every event, marriage and media item of `source` to the target, keep the
    source's names as historical names of the target (and its coordinates, region and
    country where the target has none), then move `source` to the trash. Restoring it
    from the trash undoes the merge."""
    if body.target_id == source.id:
        raise AppError("cannot_merge_into_itself")
    target = await get_place(session, source.tree_id, body.target_id)
    target_before = place_snapshot(target)
    ids = {
        key: list(await session.scalars(select(model.id).where(model.place_id == source.id)))
        for key, model in (("events", Event), ("partnerships", Partnership), ("media", MediaFile))
    }
    await _move(session, ids, target.id, None)
    moved = {key: [str(i) for i in v] for key, v in ids.items()}
    added = _merged_names(source, target)
    target.historical_names = [*(target.historical_names or []), *added]
    filled: list[str] = []
    if target.latitude is None and source.latitude is not None:
        target.latitude, target.longitude = source.latitude, source.longitude
        filled += ["latitude", "longitude"]
    for f in ("region", "country"):
        if not getattr(target, f) and getattr(source, f):
            setattr(target, f, getattr(source, f))
            filled.append(f)
    target.search_text = place_search_text(target)
    target.updated_by_id = actor.user.id if actor.user else None
    target.updated_at = utcnow()
    source.deleted_at, source.deleted_batch_id = utcnow(), source.id
    audit.record(
        session, actor, "place.update", "place", target.id, tree_id=target.tree_id,
        before=target_before, after=place_snapshot(target),
    )  # fmt: skip
    audit.record(
        session, actor, MERGED, "place", source.id, tree_id=source.tree_id,
        before=place_snapshot(source),
        after={
            "into": str(target.id), "moved": moved,
            "added_names": [h["name"] for h in added], "filled": filled,
        },
    )  # fmt: skip
    await session.commit()
    await session.refresh(target)
    return target


async def undo_merge(session: AsyncSession, source: Place) -> None:
    """Called when a place comes back from the trash: if it went there by a merge, move
    what was moved back (unless it has been moved again since) and take its names off the
    target."""
    entry = await session.scalar(
        select(AuditLog)
        .where(
            AuditLog.entity_id == source.id,
            AuditLog.action.in_((MERGED, "place.delete")),
        )
        .order_by(AuditLog.created_at.desc())
        .limit(1)
    )
    if entry is None or entry.action != MERGED or not entry.after:
        return
    target = await session.get(Place, uuid.UUID(entry.after["into"]))
    if target is None:  # pragma: no cover - rows are never hard-deleted
        return
    moved: dict[str, Sequence[str]] = entry.after.get("moved", {})
    ids = {key: [uuid.UUID(i) for i in v] for key, v in moved.items()}
    await _move(session, ids, source.id, target.id)
    added = {n.lower() for n in entry.after.get("added_names", [])}
    target.historical_names = [
        h for h in target.historical_names or [] if h.get("name", "").lower() not in added
    ]
    for f in entry.after.get("filled", []):
        if getattr(target, f) == getattr(source, f):
            setattr(target, f, None)
    target.search_text = place_search_text(target)
