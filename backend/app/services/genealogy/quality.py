"""Data-quality panel: what is missing or contradictory in a tree (research to-do list)."""

from __future__ import annotations

import uuid
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Citation,
    CitedEntity,
    Event,
    EventParticipant,
    EventType,
    ParentChild,
    Person,
    PersonName,
    QuestionStatus,
    Source,
)
from app.schemas.collaboration import DataQuality, DateProblem
from app.schemas.persons import Warning
from app.services.genealogy.collaboration import list_questions, questions_out
from app.services.genealogy.common import bounds
from app.services.genealogy.plausibility import parent_child_warnings, vital_warnings
from app.services.genealogy.summaries import summaries_for
from app.services.genealogy.vitals import Vitals, load_vitals

DEFAULT_LIMIT = 200


def _has_birth_year(v: Vitals | None) -> bool:
    return bool(v and v.birth_date and v.birth_date.year)


async def data_quality(
    session: AsyncSession, tree_id: uuid.UUID, *, limit: int = DEFAULT_LIMIT
) -> DataQuality:
    persons = list(
        await session.scalars(
            select(Person).where(Person.tree_id == tree_id, Person.deleted_at.is_(None))
        )
    )
    ids = {p.id for p in persons}
    vitals = await load_vitals(session, tree_id)
    gender = {p.id: p.gender for p in persons}

    missing_birth = [p for p in persons if not _has_birth_year(vitals.get(p.id))]
    missing_photo = [p for p in persons if p.primary_photo_id is None]

    # People with at least one citation on themselves, a name, or one of their events.
    cited: set[uuid.UUID] = set()
    live_citations = (
        select(Citation.entity_type, Citation.entity_id)
        .join(Source, Source.id == Citation.source_id)
        .where(
            Citation.tree_id == tree_id, Citation.deleted_at.is_(None), Source.deleted_at.is_(None)
        )
    )
    rows = (await session.execute(live_citations)).all()
    by_type: dict[CitedEntity, set[uuid.UUID]] = defaultdict(set)
    for etype, eid in rows:
        by_type[etype].add(eid)
    cited |= by_type[CitedEntity.person] & ids
    if by_type[CitedEntity.person_name]:
        cited |= set(
            await session.scalars(
                select(PersonName.person_id).where(
                    PersonName.id.in_(by_type[CitedEntity.person_name])
                )
            )
        )
    if by_type[CitedEntity.event]:
        cited |= set(
            await session.scalars(
                select(EventParticipant.person_id).where(
                    EventParticipant.event_id.in_(by_type[CitedEntity.event])
                )
            )
        )
    without_sources = [p for p in persons if p.id not in cited]

    # Date problems: same rules as the person page (plausibility.py), for everyone at once.
    problems: dict[uuid.UUID, list[Warning]] = defaultdict(list)
    for p in persons:
        problems[p.id] += vital_warnings(vitals.get(p.id, Vitals()), is_living=p.is_living)
    links = (
        await session.execute(
            select(ParentChild.parent_id, ParentChild.child_id).where(
                ParentChild.tree_id == tree_id, ParentChild.deleted_at.is_(None)
            )
        )
    ).all()
    for parent_id, child_id in links:
        if parent_id in ids and child_id in ids:
            ws = parent_child_warnings(
                vitals.get(parent_id, Vitals()), gender[parent_id], vitals.get(child_id, Vitals()),
                parent_id=parent_id,
            )  # fmt: skip
            problems[child_id] += ws
    events = (
        await session.execute(
            select(EventParticipant.person_id, Event)
            .join(Event, Event.id == EventParticipant.event_id)
            .where(
                Event.tree_id == tree_id,
                Event.deleted_at.is_(None),
                Event.type.notin_((EventType.birth, EventType.death)),
            )
        )
    ).all()
    for pid, ev in events:
        v = vitals.get(pid)
        if not v or pid not in ids:
            continue
        ev_lo, ev_hi = bounds(ev.date)
        b_lo = bounds(v.birth_date)[0]
        d_hi = bounds(v.death_date)[1]
        if ev.type != EventType.baptism and ev_hi and b_lo and ev_hi < b_lo:
            problems[pid].append(
                Warning(code="event_before_birth", params={"event_id": str(ev.id)})
            )
        if ev.type != EventType.burial and ev_lo and d_hi and d_hi < ev_lo:
            problems[pid].append(Warning(code="event_after_death", params={"event_id": str(ev.id)}))
    with_problems = [p for p in persons if problems[p.id]]

    open_q = await list_questions(session, tree_id, status=QuestionStatus.open)

    shown = {
        p.id: p
        for p in (
            missing_birth[:limit]
            + missing_photo[:limit]
            + without_sources[:limit]
            + with_problems[:limit]
        )
    }
    summaries = {s.id: s for s in await summaries_for(session, tree_id, list(shown.values()))}

    def by_name(group: list[Person]) -> list[Person]:
        return sorted(
            group, key=lambda p: summaries[p.id].display_name.lower() if p.id in summaries else ""
        )

    return DataQuality(
        counts={
            "people": len(persons),
            "missing_birth": len(missing_birth),
            "missing_photo": len(missing_photo),
            "without_sources": len(without_sources),
            "date_problems": len(with_problems),
            "open_questions": len(open_q),
        },
        missing_birth=[summaries[p.id] for p in by_name(missing_birth[:limit])],
        missing_photo=[summaries[p.id] for p in by_name(missing_photo[:limit])],
        without_sources=[summaries[p.id] for p in by_name(without_sources[:limit])],
        date_problems=[
            DateProblem(person=summaries[p.id], warnings=problems[p.id])
            for p in by_name(with_problems[:limit])
        ],
        open_questions=await questions_out(session, open_q[:limit]),
    )
