"""Sources and citations."""

from __future__ import annotations

import uuid
from collections.abc import Iterable, Sequence
from typing import Any

from sqlalchemy import delete, func, or_, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.core.security import utcnow
from app.models import (
    Citation,
    CitationQuality,
    CitedEntity,
    Event,
    EventParticipant,
    MediaFile,
    ParentChild,
    Partnership,
    Person,
    PersonName,
    Source,
    SourceMedia,
    SourceType,
    User,
)
from app.schemas.sources import (
    CitationCreate,
    CitationOut,
    CitationTarget,
    CitationUpdate,
    SourceCreate,
    SourceOut,
    SourceSummary,
    SourceUpdate,
)
from app.schemas.stories import UserRef
from app.services import audit
from app.services.context import Actor
from app.services.genealogy.common import get_live, name_display
from app.services.genealogy.media import media_out_many
from app.services.genealogy.summaries import summary_map
from app.services.search_text import build_search_text, query_alternatives

SOURCE_FIELDS = ("title", "type", "author", "archive_name", "reference_number", "url", "notes")
CITATION_FIELDS = ("source_id", "entity_type", "entity_id", "field", "page", "quality", "notes")

CITED_MODELS: dict[CitedEntity, type[Any]] = {
    CitedEntity.person: Person,
    CitedEntity.event: Event,
    CitedEntity.parent_child: ParentChild,
    CitedEntity.partnership: Partnership,
    CitedEntity.media: MediaFile,
}


def _plain(v: Any) -> Any:
    if isinstance(v, uuid.UUID):
        return str(v)
    return v.value if hasattr(v, "value") else v


async def user_refs(
    session: AsyncSession, ids: Iterable[uuid.UUID | None]
) -> dict[uuid.UUID, UserRef]:
    wanted = {i for i in ids if i}
    if not wanted:
        return {}
    rows = await session.execute(select(User.id, User.display_name).where(User.id.in_(wanted)))
    return {uid: UserRef(id=uid, display_name=name) for uid, name in rows.all()}


# --- Sources ----------------------------------------------------------------------------


def _index(source: Source) -> None:
    source.search_text = build_search_text(
        [source.title, source.author, source.archive_name, source.reference_number]
    )


def source_snapshot(source: Source, media_ids: Sequence[uuid.UUID]) -> dict[str, Any]:
    return {
        **{f: _plain(getattr(source, f)) for f in SOURCE_FIELDS},
        "media_ids": sorted(str(m) for m in media_ids),
    }


async def source_media_ids(session: AsyncSession, source_id: uuid.UUID) -> list[uuid.UUID]:
    return list(
        await session.scalars(
            select(SourceMedia.media_id).where(SourceMedia.source_id == source_id)
        )
    )


async def _set_source_media(
    session: AsyncSession, source: Source, media_ids: list[uuid.UUID]
) -> None:
    for mid in media_ids:
        await get_live(session, MediaFile, source.tree_id, mid, "media_not_found")
    await session.execute(delete(SourceMedia).where(SourceMedia.source_id == source.id))
    session.add_all(SourceMedia(source_id=source.id, media_id=m) for m in dict.fromkeys(media_ids))


async def get_source(session: AsyncSession, tree_id: uuid.UUID, source_id: uuid.UUID) -> Source:
    return await get_live(session, Source, tree_id, source_id, "source_not_found")


async def search_sources(
    session: AsyncSession, tree_id: uuid.UUID, q: str | None, *, limit: int, offset: int
) -> tuple[list[Source], int]:
    stmt = select(Source).where(Source.tree_id == tree_id, Source.deleted_at.is_(None))
    for alts in query_alternatives(q or ""):
        stmt = stmt.where(or_(*(Source.search_text.ilike(f"%{a}%") for a in alts)))
    total = await session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = await session.scalars(
        stmt.order_by(func.lower(Source.title), Source.id).limit(limit).offset(offset)
    )
    return list(rows), total


async def sources_out(session: AsyncSession, sources: Sequence[Source]) -> list[SourceOut]:
    if not sources:
        return []
    ids = [s.id for s in sources]
    counts = dict(
        (
            await session.execute(
                select(Citation.source_id, func.count())
                .where(Citation.source_id.in_(ids), Citation.deleted_at.is_(None))
                .group_by(Citation.source_id)
            )
        ).all()
    )
    links = (
        await session.execute(
            select(SourceMedia.source_id, MediaFile)
            .join(MediaFile, MediaFile.id == SourceMedia.media_id)
            .where(SourceMedia.source_id.in_(ids), MediaFile.deleted_at.is_(None))
        )
    ).all()
    media_out = {m.id: m for m in await media_out_many(session, [m for _, m in links])}
    return [
        SourceOut(
            id=s.id,
            title=s.title,
            type=s.type,
            author=s.author,
            archive_name=s.archive_name,
            reference_number=s.reference_number,
            url=s.url,
            notes=s.notes,
            media=[media_out[m.id] for sid, m in links if sid == s.id],
            citation_count=counts.get(s.id, 0),
            created_at=s.created_at,
            updated_at=s.updated_at,
        )
        for s in sources
    ]


async def create_source(
    session: AsyncSession,
    tree_id: uuid.UUID,
    body: SourceCreate,
    actor: Actor,
    *,
    commit: bool = True,
) -> Source:
    user_id = actor.user.id if actor.user else None
    source = Source(
        id=uuid.uuid4(),
        tree_id=tree_id,
        created_by_id=user_id,
        updated_by_id=user_id,
        **body.model_dump(exclude={"media_ids"}),
    )
    _index(source)
    session.add(source)
    await session.flush()
    await _set_source_media(session, source, body.media_ids or [])
    audit.record(
        session, actor, "source.create", "source", source.id, tree_id=tree_id,
        after=source_snapshot(source, body.media_ids or []),
    )  # fmt: skip
    if commit:
        await session.commit()
    return source


async def update_source(
    session: AsyncSession, source: Source, body: SourceUpdate, actor: Actor
) -> Source:
    before = source_snapshot(source, await source_media_ids(session, source.id))
    for f in body.model_fields_set - {"media_ids"}:
        value = getattr(body, f)
        if f in ("title", "type") and value is None:
            continue
        setattr(source, f, value)
    if body.media_ids is not None:
        await _set_source_media(session, source, body.media_ids)
    _index(source)
    source.updated_by_id = actor.user.id if actor.user else None
    source.updated_at = utcnow()
    await session.flush()
    after = source_snapshot(source, await source_media_ids(session, source.id))
    if before != after:
        audit.record(
            session, actor, "source.update", "source", source.id, tree_id=source.tree_id,
            before=before, after=after,
        )  # fmt: skip
    await session.commit()
    return source


async def apply_source_snapshot(
    session: AsyncSession, source: Source, snap: dict[str, Any]
) -> None:
    for f in SOURCE_FIELDS:
        setattr(source, f, SourceType(snap[f]) if f == "type" else snap.get(f))
    _index(source)
    await session.execute(delete(SourceMedia).where(SourceMedia.source_id == source.id))
    session.add_all(
        SourceMedia(source_id=source.id, media_id=uuid.UUID(m)) for m in snap.get("media_ids", [])
    )


async def delete_source(session: AsyncSession, source: Source, actor: Actor) -> None:
    """Soft delete; its citations go to the trash with it (same batch)."""
    now = utcnow()
    before = source_snapshot(source, await source_media_ids(session, source.id))
    for c in await session.scalars(
        select(Citation).where(Citation.source_id == source.id, Citation.deleted_at.is_(None))
    ):
        c.deleted_at, c.deleted_batch_id = now, source.id
    source.deleted_at, source.deleted_batch_id = now, source.id
    audit.record(
        session, actor, "source.delete", "source", source.id, tree_id=source.tree_id, before=before
    )
    await session.commit()


# --- Citations --------------------------------------------------------------------------


def citation_snapshot(c: Citation) -> dict[str, Any]:
    return {f: _plain(getattr(c, f)) for f in CITATION_FIELDS}


def apply_citation_snapshot(c: Citation, snap: dict[str, Any]) -> None:
    c.field, c.page, c.notes = snap.get("field"), snap.get("page"), snap.get("notes")
    c.quality = CitationQuality(snap["quality"])


async def _check_target(
    session: AsyncSession, tree_id: uuid.UUID, entity_type: CitedEntity, entity_id: uuid.UUID
) -> None:
    if entity_type == CitedEntity.person_name:
        name = await session.get(PersonName, entity_id)
        person = await session.get(Person, name.person_id) if name else None
        if person is None or person.tree_id != tree_id or person.deleted_at is not None:
            raise NotFoundError("citation_target_not_found")
        return
    await get_live(
        session, CITED_MODELS[entity_type], tree_id, entity_id, "citation_target_not_found"
    )


async def get_citation(session: AsyncSession, tree_id: uuid.UUID, cid: uuid.UUID) -> Citation:
    return await get_live(session, Citation, tree_id, cid, "citation_not_found")


async def create_citation(
    session: AsyncSession,
    tree_id: uuid.UUID,
    body: CitationCreate,
    actor: Actor,
    *,
    commit: bool = True,
) -> Citation:
    await get_source(session, tree_id, body.source_id)
    await _check_target(session, tree_id, body.entity_type, body.entity_id)
    duplicate = await session.scalar(
        select(Citation.id).where(
            Citation.source_id == body.source_id,
            Citation.entity_type == body.entity_type,
            Citation.entity_id == body.entity_id,
            Citation.field.is_not_distinct_from(body.field),
            Citation.page.is_not_distinct_from(body.page),
            Citation.deleted_at.is_(None),
        )
    )
    if duplicate:
        raise ConflictError("citation_exists")
    user_id = actor.user.id if actor.user else None
    c = Citation(
        id=uuid.uuid4(),
        tree_id=tree_id,
        source_id=body.source_id,
        entity_type=body.entity_type,
        entity_id=body.entity_id,
        field=body.field,
        page=body.page,
        quality=body.quality or CitationQuality.unverified,
        notes=body.notes,
        created_by_id=user_id,
        updated_by_id=user_id,
    )
    session.add(c)
    await session.flush()
    audit.record(
        session, actor, "citation.create", "citation", c.id, tree_id=tree_id,
        after=citation_snapshot(c),
    )  # fmt: skip
    if commit:
        await session.commit()
    return c


async def update_citation(
    session: AsyncSession, c: Citation, body: CitationUpdate, actor: Actor
) -> Citation:
    before = citation_snapshot(c)
    for f in body.model_fields_set:
        value = getattr(body, f)
        if f == "quality" and value is None:
            continue
        setattr(c, f, value)
    c.updated_by_id = actor.user.id if actor.user else None
    after = citation_snapshot(c)
    if before != after:
        audit.record(
            session, actor, "citation.update", "citation", c.id, tree_id=c.tree_id,
            before=before, after=after,
        )  # fmt: skip
    await session.commit()
    return c


async def delete_citation(session: AsyncSession, c: Citation, actor: Actor) -> None:
    c.deleted_at, c.deleted_batch_id = utcnow(), c.id
    audit.record(
        session, actor, "citation.delete", "citation", c.id, tree_id=c.tree_id,
        before=citation_snapshot(c),
    )  # fmt: skip
    await session.commit()


async def _targets(
    session: AsyncSession, tree_id: uuid.UUID, citations: Sequence[Citation]
) -> dict[uuid.UUID, CitationTarget]:
    """Neutral descriptions of what each citation supports (codes; the UI translates)."""
    by_type: dict[CitedEntity, set[uuid.UUID]] = {}
    for c in citations:
        by_type.setdefault(c.entity_type, set()).add(c.entity_id)
    labels: dict[uuid.UUID, CitationTarget] = {}
    person_ids: set[uuid.UUID] = set(by_type.get(CitedEntity.person, set()))
    pcs = list(
        await session.scalars(
            select(ParentChild).where(
                ParentChild.id.in_(by_type.get(CitedEntity.parent_child, set()))
            )
        )
    )
    pas = list(
        await session.scalars(
            select(Partnership).where(
                Partnership.id.in_(by_type.get(CitedEntity.partnership, set()))
            )
        )
    )
    for pc in pcs:
        person_ids |= {pc.parent_id, pc.child_id}
    for pa in pas:
        person_ids |= {pa.person_a_id, pa.person_b_id}
    names = await summary_map(session, tree_id, person_ids)

    def nm(pid: uuid.UUID) -> str:
        return names[pid].display_name if pid in names else "?"

    for pid in by_type.get(CitedEntity.person, set()):
        labels[pid] = CitationTarget(entity_type=CitedEntity.person, entity_id=pid, label=nm(pid))
    for n in await session.scalars(
        select(PersonName).where(PersonName.id.in_(by_type.get(CitedEntity.person_name, set())))
    ):
        labels[n.id] = CitationTarget(
            entity_type=CitedEntity.person_name, entity_id=n.id, label=name_display(n)
        )
    for ev in await session.scalars(
        select(Event).where(Event.id.in_(by_type.get(CitedEntity.event, set())))
    ):
        labels[ev.id] = CitationTarget(
            entity_type=CitedEntity.event, entity_id=ev.id, event_type=ev.type.value,
            date=ev.date.to_text() or None, label=ev.title,
        )  # fmt: skip
    for pc in pcs:
        labels[pc.id] = CitationTarget(
            entity_type=CitedEntity.parent_child,
            entity_id=pc.id,
            label=f"{nm(pc.parent_id)} → {nm(pc.child_id)}",
        )
    for pa in pas:
        labels[pa.id] = CitationTarget(
            entity_type=CitedEntity.partnership,
            entity_id=pa.id,
            label=f"{nm(pa.person_a_id)} ⚭ {nm(pa.person_b_id)}",
        )
    for m in await session.scalars(
        select(MediaFile).where(MediaFile.id.in_(by_type.get(CitedEntity.media, set())))
    ):
        labels[m.id] = CitationTarget(
            entity_type=CitedEntity.media, entity_id=m.id, label=m.title or m.original_filename
        )
    return labels


async def citations_out(
    session: AsyncSession, tree_id: uuid.UUID, citations: Sequence[Citation]
) -> list[CitationOut]:
    if not citations:
        return []
    sources = {
        s.id: s
        for s in await session.scalars(
            select(Source).where(Source.id.in_({c.source_id for c in citations}))
        )
    }
    targets = await _targets(session, tree_id, citations)
    return [
        CitationOut(
            id=c.id,
            source=SourceSummary(
                id=c.source_id, title=sources[c.source_id].title, type=sources[c.source_id].type
            ),
            target=targets.get(
                c.entity_id, CitationTarget(entity_type=c.entity_type, entity_id=c.entity_id)
            ),
            field=c.field,
            page=c.page,
            quality=c.quality,
            notes=c.notes,
            created_at=c.created_at,
        )
        for c in citations
    ]


async def list_citations(
    session: AsyncSession,
    tree_id: uuid.UUID,
    *,
    entity_type: CitedEntity | None = None,
    entity_id: uuid.UUID | None = None,
    source_id: uuid.UUID | None = None,
) -> list[Citation]:
    stmt = (
        select(Citation)
        .join(Source, Source.id == Citation.source_id)
        .where(
            Citation.tree_id == tree_id, Citation.deleted_at.is_(None), Source.deleted_at.is_(None)
        )
    )
    if entity_type:
        stmt = stmt.where(Citation.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(Citation.entity_id == entity_id)
    if source_id:
        stmt = stmt.where(Citation.source_id == source_id)
    return list(await session.scalars(stmt.order_by(Citation.created_at)))


async def person_fact_keys(
    session: AsyncSession, person: Person
) -> list[tuple[CitedEntity, uuid.UUID]]:
    """Everything about a person a citation can be attached to."""
    keys: list[tuple[CitedEntity, uuid.UUID]] = [(CitedEntity.person, person.id)]
    keys += [
        (CitedEntity.person_name, i)
        for i in await session.scalars(
            select(PersonName.id).where(PersonName.person_id == person.id)
        )
    ]
    keys += [
        (CitedEntity.event, i)
        for i in await session.scalars(
            select(Event.id)
            .join(EventParticipant, EventParticipant.event_id == Event.id)
            .where(EventParticipant.person_id == person.id, Event.deleted_at.is_(None))
        )
    ]
    keys += [
        (CitedEntity.parent_child, i)
        for i in await session.scalars(
            select(ParentChild.id).where(
                or_(ParentChild.parent_id == person.id, ParentChild.child_id == person.id),
                ParentChild.deleted_at.is_(None),
            )
        )
    ]
    keys += [
        (CitedEntity.partnership, i)
        for i in await session.scalars(
            select(Partnership.id).where(
                or_(Partnership.person_a_id == person.id, Partnership.person_b_id == person.id),
                Partnership.deleted_at.is_(None),
            )
        )
    ]
    return keys


async def person_citations(session: AsyncSession, person: Person) -> list[Citation]:
    keys = await person_fact_keys(session, person)
    return list(
        await session.scalars(
            select(Citation)
            .join(Source, Source.id == Citation.source_id)
            .where(
                tuple_(Citation.entity_type, Citation.entity_id).in_(keys),
                Citation.deleted_at.is_(None),
                Source.deleted_at.is_(None),
            )
            .order_by(Citation.created_at)
        )
    )
