"""Compact person summaries (name + life dates), loaded in a fixed number of queries."""

from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Person, PersonName
from app.schemas.dates import PartialDateOut
from app.schemas.persons import PersonSummary
from app.services.genealogy.common import name_display, pick_primary
from app.services.genealogy.vitals import Vitals, load_vitals


async def load_names(
    session: AsyncSession, person_ids: Iterable[uuid.UUID] | None, tree_id: uuid.UUID
) -> dict[uuid.UUID, list[PersonName]]:
    stmt = select(PersonName)
    if person_ids is None:
        stmt = stmt.join(Person, Person.id == PersonName.person_id).where(Person.tree_id == tree_id)
    else:
        ids = list(person_ids)
        if not ids:
            return {}
        stmt = stmt.where(PersonName.person_id.in_(ids))
    result: dict[uuid.UUID, list[PersonName]] = defaultdict(list)
    for name in await session.scalars(stmt):
        result[name.person_id].append(name)
    return result


def make_summary(person: Person, names: list[PersonName], vitals: Vitals) -> PersonSummary:
    birth_place = vitals.birth.place.name if vitals.birth and vitals.birth.place else None
    return PersonSummary(
        id=person.id,
        display_name=name_display(pick_primary(names)),
        gender=person.gender,
        is_living=person.is_living,
        birth=PartialDateOut.from_domain(vitals.birth_date),
        death=PartialDateOut.from_domain(vitals.death_date),
        birth_place=birth_place,
        primary_photo_id=person.primary_photo_id,
    )


async def summaries_for(
    session: AsyncSession, tree_id: uuid.UUID, persons: list[Person], *, whole_tree: bool = False
) -> list[PersonSummary]:
    ids = None if whole_tree else [p.id for p in persons]
    names = await load_names(session, ids, tree_id)
    vitals = await load_vitals(session, tree_id, ids)
    return [make_summary(p, names.get(p.id, []), vitals.get(p.id, Vitals())) for p in persons]


async def summary_map(
    session: AsyncSession, tree_id: uuid.UUID, person_ids: Iterable[uuid.UUID]
) -> dict[uuid.UUID, PersonSummary]:
    ids = set(person_ids)
    if not ids:
        return {}
    persons = list(
        await session.scalars(select(Person).where(Person.id.in_(ids), Person.deleted_at.is_(None)))
    )
    return {s.id: s for s in await summaries_for(session, tree_id, persons)}
