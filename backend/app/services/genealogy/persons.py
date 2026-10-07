"""People: create / update / read (with relatives, timeline, warnings) / search."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dates import PartialDate
from app.core.security import utcnow
from app.models import (
    Event,
    EventParticipant,
    EventType,
    Gender,
    ParentChild,
    Partnership,
    Person,
    PersonName,
    Place,
    ResearchStatus,
)
from app.schemas.dates import PartialDateOut
from app.schemas.events import EventOut, ParticipantOut
from app.schemas.media import Region
from app.schemas.persons import (
    NameIn,
    NameOut,
    ParentRef,
    PartnerRef,
    PersonCreate,
    PersonDetail,
    PersonSummary,
    PersonUpdate,
    SiblingRef,
    VitalIn,
    VitalOut,
)
from app.schemas.places import PlaceSummary
from app.services import audit
from app.services.context import Actor
from app.services.genealogy import media as media_service
from app.services.genealogy.common import get_live, name_display, pick_primary, to_partial
from app.services.genealogy.media_urls import avatar_url, primary_media_map
from app.services.genealogy.plausibility import person_warnings
from app.services.genealogy.snapshots import make_names, person_snapshot
from app.services.genealogy.summaries import load_names, summaries_for, summary_map
from app.services.genealogy.vitals import set_vital, vitals_of
from app.services.search_text import query_alternatives

# People born longer ago than this, with no death recorded, are presumed dead.
PRESUMED_DEAD_AFTER_YEARS = 110


def presume_living(birth: PartialDate | None, has_death: bool) -> bool:
    """Default for `is_living` when the editor doesn't say. Errs on the side of privacy:
    unknown birth date → living (details hidden from share links / exports)."""
    if has_death:
        return False
    if birth is not None and birth.year is not None:
        return birth.year > utcnow().year - PRESUMED_DEAD_AFTER_YEARS
    return True


def _user_id(actor: Actor) -> uuid.UUID | None:
    return actor.user.id if actor.user else None


async def get_person(session: AsyncSession, tree_id: uuid.UUID, person_id: uuid.UUID) -> Person:
    return await get_live(session, Person, tree_id, person_id, "person_not_found")


async def snapshot_of(session: AsyncSession, person: Person) -> dict[str, Any]:
    names = (await load_names(session, [person.id], person.tree_id)).get(person.id, [])
    return person_snapshot(person, names, await vitals_of(session, person))


async def _apply_vital(
    session: AsyncSession,
    person: Person,
    etype: EventType,
    vital: VitalIn | None,
    *,
    remove: bool,
    actor: Actor,
) -> None:
    await set_vital(
        session,
        person,
        etype,
        date=to_partial(vital.date) if vital else None,
        place_id=vital.place_id if vital else None,
        description=vital.description if vital else None,
        remove=remove,
        user_id=_user_id(actor),
    )


def _names_payload(names: Sequence[NameIn]) -> list[dict[str, Any]]:
    return [n.model_dump(mode="json") for n in names]


async def create_person(
    session: AsyncSession,
    tree_id: uuid.UUID,
    body: PersonCreate,
    actor: Actor,
    *,
    commit: bool = True,
) -> Person:
    birth = to_partial(body.birth.date) if body.birth else None
    person = Person(
        id=uuid.uuid4(),
        tree_id=tree_id,
        gender=body.gender or Gender.unknown,
        is_living=(
            body.is_living
            if body.is_living is not None
            else presume_living(birth, body.death is not None)
        ),
        research_status=body.research_status or ResearchStatus.unknown,
        short_summary=body.short_summary,
        biography=body.biography,
        occupation=body.occupation,
        education=body.education,
        religion=body.religion,
        nationality=body.nationality,
        notes_for_descendants=body.notes_for_descendants,
        created_by_id=_user_id(actor),
        updated_by_id=_user_id(actor),
    )
    person.names = make_names(person, _names_payload(body.names))
    session.add(person)
    await session.flush()
    if body.birth:
        await _apply_vital(session, person, EventType.birth, body.birth, remove=False, actor=actor)
    if body.death:
        await _apply_vital(session, person, EventType.death, body.death, remove=False, actor=actor)
    await session.flush()
    audit.record(
        session,
        actor,
        "person.create",
        "person",
        person.id,
        tree_id=tree_id,
        after=await snapshot_of(session, person),
    )
    if commit:
        await session.commit()
    return person


SIMPLE_FIELDS = (
    "short_summary",
    "biography",
    "occupation",
    "education",
    "religion",
    "nationality",
    "notes_for_descendants",
)


async def update_person(
    session: AsyncSession, person: Person, body: PersonUpdate, actor: Actor
) -> Person:
    before = await snapshot_of(session, person)
    fields = body.model_fields_set
    for f in SIMPLE_FIELDS:
        if f in fields:
            setattr(person, f, getattr(body, f))
    if body.gender is not None:
        person.gender = body.gender
    if body.research_status is not None:
        person.research_status = body.research_status
    if body.is_living is not None:
        person.is_living = body.is_living
    elif "death" in fields and body.death is not None:
        person.is_living = False
    if "primary_photo_id" in fields or "primary_photo_crop" in fields:
        await media_service.set_primary_photo(
            session,
            person,
            body.primary_photo_id if "primary_photo_id" in fields else person.primary_photo_id,
            body.primary_photo_crop,
        )
    if body.names is not None:
        await session.refresh(person, ["names"])
        person.names = make_names(person, _names_payload(body.names))
    for key, etype in (("birth", EventType.birth), ("death", EventType.death)):
        if key in fields:
            vital = getattr(body, key)
            await _apply_vital(session, person, etype, vital, remove=vital is None, actor=actor)
    person.updated_by_id = _user_id(actor)
    person.updated_at = utcnow()
    await session.flush()
    after = await snapshot_of(session, person)
    if before != after:
        audit.record(
            session,
            actor,
            "person.update",
            "person",
            person.id,
            tree_id=person.tree_id,
            before=before,
            after=after,
        )
    await session.commit()
    return person


# --- Reading ----------------------------------------------------------------------------


def _vital_out(ev: Event | None) -> VitalOut | None:
    if ev is None:
        return None
    return VitalOut(
        event_id=ev.id,
        date=PartialDateOut.from_domain(ev.date),
        place=PlaceSummary.model_validate(ev.place) if ev.place else None,
        description=ev.description,
    )


async def events_out(
    session: AsyncSession, tree_id: uuid.UUID, events: Sequence[Event]
) -> list[EventOut]:
    person_ids = {p.person_id for ev in events for p in ev.participants}
    summaries = await summary_map(session, tree_id, person_ids)
    out = []
    for ev in events:
        out.append(
            EventOut(
                id=ev.id,
                type=ev.type,
                title=ev.title,
                description=ev.description,
                date=PartialDateOut.from_domain(ev.date),
                place=PlaceSummary.model_validate(ev.place) if ev.place else None,
                cemetery_name=ev.cemetery_name,
                burial_plot=ev.burial_plot,
                latitude=ev.latitude,
                longitude=ev.longitude,
                participants=[
                    ParticipantOut(
                        person_id=p.person_id,
                        role=p.role,
                        display_name=summaries[p.person_id].display_name,
                    )
                    for p in ev.participants
                    if p.person_id in summaries  # hide deleted people
                ],
                created_at=ev.created_at,
                updated_at=ev.updated_at,
            )
        )
    return out


async def person_events(session: AsyncSession, person: Person) -> list[Event]:
    """The person's timeline: all live events they take part in, in date order."""
    rows = await session.scalars(
        select(Event)
        .join(EventParticipant, EventParticipant.event_id == Event.id)
        .options(selectinload(Event.place), selectinload(Event.participants))
        .where(EventParticipant.person_id == person.id, Event.deleted_at.is_(None))
        .order_by(Event.date_sort.asc().nulls_last(), Event.created_at)
    )
    return list(rows.unique())


async def _relatives(
    session: AsyncSession, person: Person
) -> tuple[list[ParentChild], list[ParentChild], list[Partnership], list[ParentChild]]:
    live_person = select(Person.id).where(Person.deleted_at.is_(None))
    parents = list(
        await session.scalars(
            select(ParentChild).where(
                ParentChild.child_id == person.id,
                ParentChild.deleted_at.is_(None),
                ParentChild.parent_id.in_(live_person),
            )
        )
    )
    children = list(
        await session.scalars(
            select(ParentChild).where(
                ParentChild.parent_id == person.id,
                ParentChild.deleted_at.is_(None),
                ParentChild.child_id.in_(live_person),
            )
        )
    )
    partners = list(
        await session.scalars(
            select(Partnership)
            .where(
                or_(Partnership.person_a_id == person.id, Partnership.person_b_id == person.id),
                Partnership.deleted_at.is_(None),
                Partnership.person_a_id.in_(live_person),
                Partnership.person_b_id.in_(live_person),
            )
            .order_by(Partnership.start_sort.asc().nulls_last())
        )
    )
    parent_ids = [p.parent_id for p in parents]
    sibling_links = (
        list(
            await session.scalars(
                select(ParentChild).where(
                    ParentChild.parent_id.in_(parent_ids),
                    ParentChild.child_id != person.id,
                    ParentChild.deleted_at.is_(None),
                    ParentChild.child_id.in_(live_person),
                )
            )
        )
        if parent_ids
        else []
    )
    return parents, children, partners, sibling_links


async def person_detail(session: AsyncSession, person: Person) -> PersonDetail:
    names = (await load_names(session, [person.id], person.tree_id)).get(person.id, [])
    media_items, _ = await media_service.list_media(
        session, person.tree_id, person_id=person.id, kind=None, q=None, limit=10_000, offset=0
    )
    photos = await primary_media_map(session, [person])
    primary = photos.get(person.primary_photo_id) if person.primary_photo_id else None
    vitals = await vitals_of(session, person)
    events = await person_events(session, person)
    parents, children, partners, sibling_links = await _relatives(session, person)

    related_ids = (
        {p.parent_id for p in parents}
        | {c.child_id for c in children}
        | {p.person_a_id for p in partners}
        | {p.person_b_id for p in partners}
        | {s.child_id for s in sibling_links}
    ) - {person.id}
    summaries = await summary_map(session, person.tree_id, related_ids)

    my_parents = {p.parent_id for p in parents}
    sibling_parents: dict[uuid.UUID, set[uuid.UUID]] = {}
    for link in sibling_links:
        sibling_parents.setdefault(link.child_id, set()).add(link.parent_id)
    siblings = sorted(
        (
            SiblingRef(half=parent_set != my_parents, person=summaries[sid])
            for sid, parent_set in sibling_parents.items()
            if sid in summaries
        ),
        key=lambda s: (
            s.person.birth.sort if s.person.birth and s.person.birth.sort else utcnow().date()
        ),
    )

    def ref(link: ParentChild, other: uuid.UUID) -> ParentRef:
        return ParentRef(relationship_id=link.id, type=link.type, person=summaries[other])

    return PersonDetail(
        id=person.id,
        tree_id=person.tree_id,
        display_name=name_display(pick_primary(names)),
        gender=person.gender,
        is_living=person.is_living,
        short_summary=person.short_summary,
        biography=person.biography,
        occupation=person.occupation,
        education=person.education,
        religion=person.religion,
        nationality=person.nationality,
        notes_for_descendants=person.notes_for_descendants,
        research_status=person.research_status,
        primary_photo_id=person.primary_photo_id,
        primary_photo_crop=Region.model_validate(person.primary_photo_crop)
        if person.primary_photo_crop
        else None,
        avatar_url=avatar_url(person, primary),
        portrait_pending=person.primary_photo_id is not None and person.avatar_key is None,
        media=await media_service.media_out_many(session, media_items),
        names=[_name_out(n) for n in sorted(names, key=lambda n: (not n.is_primary, n.sort_order))],
        birth=_vital_out(vitals.birth),
        death=_vital_out(vitals.death),
        events=await events_out(session, person.tree_id, events),
        parents=[ref(p, p.parent_id) for p in parents if p.parent_id in summaries],
        children=sorted(
            (ref(c, c.child_id) for c in children if c.child_id in summaries),
            key=lambda r: (
                r.person.birth.sort if r.person.birth and r.person.birth.sort else utcnow().date()
            ),
        ),
        partners=[
            PartnerRef(
                partnership_id=p.id,
                type=p.type,
                start_date=PartialDateOut.from_domain(p.start_date),
                end_date=PartialDateOut.from_domain(p.end_date),
                end_reason=p.end_reason,
                person=summaries[other],
            )
            for p in partners
            if (other := p.person_b_id if p.person_a_id == person.id else p.person_a_id)
            in summaries
        ],
        siblings=siblings,
        warnings=await person_warnings(session, person),
        created_at=person.created_at,
        updated_at=person.updated_at,
    )


def _name_out(n: PersonName) -> NameOut:
    return NameOut(
        id=n.id,
        type=n.type,
        first_name=n.first_name,
        middle_name=n.middle_name,
        patronymic=n.patronymic,
        last_name=n.last_name,
        maiden_name=n.maiden_name,
        script=n.script,
        is_primary=n.is_primary,
        notes=n.notes,
        display=name_display(n),
    )


async def search_persons(
    session: AsyncSession,
    tree_id: uuid.UUID,
    q: str | None,
    *,
    limit: int,
    offset: int,
) -> tuple[list[PersonSummary], int]:
    """Each query term must match a name variant (Cyrillic or Latin, any name type) or the
    place of one of the person's events; 4-digit terms match birth/death years."""
    stmt = select(Person).where(Person.tree_id == tree_id, Person.deleted_at.is_(None))
    alternatives = query_alternatives(q or "")
    years = [int(a[0]) for a in alternatives if len(a) == 1 and a[0].isdigit() and len(a[0]) == 4]
    name_terms = [a for a in alternatives if not (len(a) == 1 and a[0].isdigit())]
    for alts in name_terms:
        by_name = select(PersonName.person_id).where(
            or_(*(PersonName.search_text.ilike(f"%{a}%") for a in alts))
        )
        # ...or the place (incl. historical names) of any of the person's life events.
        by_place = (
            select(EventParticipant.person_id)
            .join(Event, Event.id == EventParticipant.event_id)
            .join(Place, Place.id == Event.place_id)
            .where(
                Event.tree_id == tree_id,
                Event.deleted_at.is_(None),
                or_(*(Place.search_text.ilike(f"%{a}%") for a in alts)),
            )
        )
        stmt = stmt.where(or_(Person.id.in_(by_name), Person.id.in_(by_place)))
    for year in years:
        in_year = (
            select(EventParticipant.person_id)
            .join(Event, Event.id == EventParticipant.event_id)
            .where(
                Event.deleted_at.is_(None),
                Event.type.in_((EventType.birth, EventType.death)),
                Event.tree_id == tree_id,
                or_(
                    func.extract("year", Event.date_sort) == year,
                    Event.__table__.c.date_end_year == year,
                ),
            )
        )
        stmt = stmt.where(Person.id.in_(in_year))
    total = await session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    persons = list(await session.scalars(stmt.order_by(Person.created_at, Person.id)))
    summaries = await summaries_for(session, tree_id, persons)
    summaries.sort(key=lambda s: s.display_name.lower())
    return summaries[offset : offset + limit], total
