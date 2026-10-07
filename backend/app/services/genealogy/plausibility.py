"""Soft validation: implausible dates produce *warnings*, never errors.

Genealogical sources are often contradictory; the archive must accept what the sources
say and flag it for research. Checks only fire when a date is *definitely* implausible
given the precision of the dates involved (approximate dates get ±5 years of slack).
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dates import PartialDate, years_between
from app.core.security import utcnow
from app.models import Event, EventParticipant, EventType, Gender, ParentChild, Person
from app.schemas.persons import Warning
from app.services.genealogy.common import bounds
from app.services.genealogy.vitals import Vitals, load_vitals

MIN_PARENT_AGE = 12
MAX_MOTHER_AGE = 60
MAX_FATHER_AGE = 90
MAX_LIFESPAN = 120
# A child can be born up to ~10 months after the father's death.
FATHER_DEATH_GRACE_DAYS = 300


def _before(a: PartialDate | None, b: PartialDate | None) -> bool:
    """True if `a` is certainly earlier than `b`."""
    a_hi, b_lo = bounds(a)[1], bounds(b)[0]
    return a_hi is not None and b_lo is not None and a_hi < b_lo


def _min_years(a: PartialDate | None, b: PartialDate | None) -> int | None:
    """Smallest possible number of whole years from a to b."""
    a_hi, b_lo = bounds(a)[1], bounds(b)[0]
    return years_between(a_hi, b_lo) if a_hi and b_lo else None


def _max_years(a: PartialDate | None, b: PartialDate | None) -> int | None:
    a_lo, b_hi = bounds(a)[0], bounds(b)[1]
    return years_between(a_lo, b_hi) if a_lo and b_hi else None


def vital_warnings(v: Vitals, *, is_living: bool, today: date | None = None) -> list[Warning]:
    out: list[Warning] = []
    if _before(v.death_date, v.birth_date):
        out.append(Warning(code="death_before_birth"))
    lifespan = _min_years(v.birth_date, v.death_date)
    if lifespan is not None and lifespan > MAX_LIFESPAN:
        out.append(Warning(code="lifespan_too_long", params={"years": lifespan}))
    if is_living and v.death is None:
        b_hi = bounds(v.birth_date)[1]
        age = years_between(b_hi, today or utcnow().date()) if b_hi else None
        if age is not None and age > MAX_LIFESPAN:
            out.append(Warning(code="living_too_old", params={"years": age}))
    return out


def parent_child_warnings(
    parent: Vitals, parent_gender: Gender, child: Vitals, *, parent_id: uuid.UUID
) -> list[Warning]:
    p = {"parent_id": str(parent_id)}
    out: list[Warning] = []
    if _before(child.birth_date, parent.birth_date):
        out.append(Warning(code="child_born_before_parent", params=p))
    else:
        max_age = _max_years(parent.birth_date, child.birth_date)
        if max_age is not None and 0 <= max_age < MIN_PARENT_AGE:
            out.append(Warning(code="parent_too_young", params={**p, "age": max_age}))
        min_age = _min_years(parent.birth_date, child.birth_date)
        limit = MAX_MOTHER_AGE if parent_gender == Gender.female else MAX_FATHER_AGE
        if min_age is not None and min_age > limit:
            out.append(Warning(code="parent_too_old", params={**p, "age": min_age}))
    death_hi = bounds(parent.death_date)[1]
    child_lo = bounds(child.birth_date)[0]
    if death_hi and child_lo:
        grace = FATHER_DEATH_GRACE_DAYS if parent_gender != Gender.female else 0
        if (child_lo - death_hi).days > grace:
            out.append(Warning(code="born_after_parent_death", params=p))
    return out


async def event_warnings(session: AsyncSession, person_id: uuid.UUID, v: Vitals) -> list[Warning]:
    """Life events dated before birth or after death (burial etc. excluded)."""
    rows = await session.scalars(
        select(Event)
        .join(EventParticipant, EventParticipant.event_id == Event.id)
        .where(
            EventParticipant.person_id == person_id,
            Event.deleted_at.is_(None),
            Event.type.notin_((EventType.birth, EventType.death)),
        )
    )
    out: list[Warning] = []
    for ev in rows:
        if ev.type != EventType.baptism and _before(ev.date, v.birth_date):
            out.append(Warning(code="event_before_birth", params={"event_id": str(ev.id)}))
        if ev.type != EventType.burial and _before(v.death_date, ev.date):
            out.append(Warning(code="event_after_death", params={"event_id": str(ev.id)}))
    return out


async def person_warnings(session: AsyncSession, person: Person) -> list[Warning]:
    links = (
        await session.execute(
            select(ParentChild.parent_id, ParentChild.child_id).where(
                (ParentChild.parent_id == person.id) | (ParentChild.child_id == person.id),
                ParentChild.deleted_at.is_(None),
            )
        )
    ).all()
    related = {pid for pid, cid in links} | {cid for pid, cid in links} | {person.id}
    vitals = await load_vitals(session, person.tree_id, related)
    genders = dict(
        (
            await session.execute(select(Person.id, Person.gender).where(Person.id.in_(related)))
        ).all()
    )
    me = vitals.get(person.id, Vitals())
    out = vital_warnings(me, is_living=person.is_living)
    for parent_id, child_id in links:
        out += parent_child_warnings(
            vitals.get(parent_id, Vitals()),
            genders.get(parent_id, Gender.unknown),
            vitals.get(child_id, Vitals()),
            parent_id=parent_id,
        )
    out += await event_warnings(session, person.id, me)
    return out


async def link_warnings(
    session: AsyncSession, tree_id: uuid.UUID, parent: Person, child_id: uuid.UUID
) -> list[Warning]:
    vitals = await load_vitals(session, tree_id, [parent.id, child_id])
    return parent_child_warnings(
        vitals.get(parent.id, Vitals()),
        parent.gender,
        vitals.get(child_id, Vitals()),
        parent_id=parent.id,
    )
