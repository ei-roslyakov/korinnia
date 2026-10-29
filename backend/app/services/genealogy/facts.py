"""Dated facts of a whole tree — events plus the start / end of partnerships — and the
views built on them: the family timeline, the map and "on this day".

Marriages are usually recorded on the partnership itself (start date and place), not as a
separate event, so partnerships are turned into facts too. If a marriage / divorce event
for the same couple also exists, the event wins and the partnership fact is dropped.

Trees are small (≤ a few thousand people), so facts are loaded once and filtered in
Python; every view stays a fixed number of queries.
"""

from __future__ import annotations

import calendar
import datetime as dt
import uuid
from collections.abc import Collection, Iterable
from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dates import PartialDate
from app.models import (
    DatePrecision,
    Event,
    EventType,
    ParticipantRole,
    Partnership,
    PartnershipEndReason,
    Person,
    Place,
)
from app.schemas.dates import PartialDateOut
from app.schemas.insights import (
    Anniversary,
    Fact,
    FactKind,
    FactPerson,
    MapData,
    MapPoint,
    OnThisDay,
    TimelinePage,
)
from app.schemas.places import PlaceSummary
from app.services.genealogy.common import name_display, pick_primary
from app.services.genealogy.summaries import load_names

MAX_WINDOW_DAYS = 92  # three months


@dataclass(slots=True)
class FactRow:
    kind: FactKind
    id: uuid.UUID
    type: str
    title: str | None
    date: PartialDate
    place: Place | None
    persons: list[tuple[uuid.UUID, ParticipantRole]]
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    cemetery_name: str | None = None
    sort: dt.date | None = field(init=False)

    def __post_init__(self) -> None:
        self.sort = None if self.date.is_empty else self.date.sort_key()

    def involves(self, person_id: uuid.UUID) -> bool:
        return any(pid == person_id for pid, _ in self.persons)


@dataclass(slots=True)
class Facts:
    rows: list[FactRow]
    names: dict[uuid.UUID, str]

    def out(self, row: FactRow) -> Fact:
        return Fact(
            kind=row.kind,
            id=row.id,
            type=row.type,
            title=row.title,
            date=PartialDateOut.from_domain(row.date),
            place=PlaceSummary.model_validate(row.place) if row.place else None,
            latitude=row.latitude,
            longitude=row.longitude,
            cemetery_name=row.cemetery_name,
            persons=[
                FactPerson(id=pid, display_name=self.names[pid], role=role)
                for pid, role in row.persons
            ],
        )


def _partnership_end_type(reason: PartnershipEndReason | None) -> str | None:
    if reason in (PartnershipEndReason.divorce, PartnershipEndReason.separation):
        return reason.value
    if reason == PartnershipEndReason.death:
        return None  # the death itself is already a fact
    return "partnership_end"


async def load_facts(
    session: AsyncSession, tree_id: uuid.UUID, hidden: Collection[uuid.UUID] = ()
) -> Facts:
    """All dated and undated facts; facts involving `hidden` people (living, for readers
    who see only their basics) are left out."""
    facts = await _load_facts(session, tree_id)
    if hidden:
        facts.rows = [r for r in facts.rows if not any(pid in hidden for pid, _ in r.persons)]
    return facts


async def _load_facts(session: AsyncSession, tree_id: uuid.UUID) -> Facts:
    live = set(
        await session.scalars(
            select(Person.id).where(Person.tree_id == tree_id, Person.deleted_at.is_(None))
        )
    )
    names = {
        pid: name_display(pick_primary(ns))
        for pid, ns in (await load_names(session, None, tree_id)).items()
        if pid in live
    }
    for pid in live - names.keys():
        names[pid] = "?"

    rows: list[FactRow] = []
    couples_with_event: dict[str, set[frozenset[uuid.UUID]]] = {"marriage": set(), "divorce": set()}
    events = await session.scalars(
        select(Event)
        .options(selectinload(Event.place), selectinload(Event.participants))
        .where(Event.tree_id == tree_id, Event.deleted_at.is_(None))
    )
    for ev in events:
        persons = [(p.person_id, p.role) for p in ev.participants if p.person_id in live]
        if not persons:
            continue
        if ev.type in (EventType.marriage, EventType.divorce):
            couples_with_event[ev.type.value].add(frozenset(pid for pid, _ in persons))
        rows.append(
            FactRow(
                kind="event",
                id=ev.id,
                type=ev.type.value,
                title=ev.title,
                date=ev.date,
                place=ev.place if ev.place and ev.place.deleted_at is None else None,
                persons=persons,
                latitude=ev.latitude,
                longitude=ev.longitude,
                cemetery_name=ev.cemetery_name,
            )
        )

    partnerships = list(
        await session.scalars(
            select(Partnership).where(
                Partnership.tree_id == tree_id, Partnership.deleted_at.is_(None)
            )
        )
    )
    place_ids = {p.place_id for p in partnerships if p.place_id}
    places = (
        {
            pl.id: pl
            for pl in await session.scalars(
                select(Place).where(Place.id.in_(place_ids), Place.deleted_at.is_(None))
            )
        }
        if place_ids
        else {}
    )

    def covered(kind: str, couple: frozenset[uuid.UUID]) -> bool:
        return any(couple <= people for people in couples_with_event[kind])

    for p in partnerships:
        if p.person_a_id not in live or p.person_b_id not in live:
            continue
        couple = frozenset((p.person_a_id, p.person_b_id))
        persons = [
            (p.person_a_id, ParticipantRole.principal),
            (p.person_b_id, ParticipantRole.principal),
        ]
        place = places.get(p.place_id) if p.place_id else None
        if not p.start_date.is_empty and not covered("marriage", couple):
            rows.append(
                FactRow(
                    kind="partnership_start",
                    id=p.id,
                    type=p.type.value,
                    title=None,
                    date=p.start_date,
                    place=place,
                    persons=persons,
                )
            )
        end_type = _partnership_end_type(p.end_reason)
        if end_type and not p.end_date.is_empty and not covered("divorce", couple):
            rows.append(
                FactRow(
                    kind="partnership_end",
                    id=p.id,
                    type=end_type,
                    title=None,
                    date=p.end_date,
                    place=None,
                    persons=persons,
                )
            )
    return Facts(rows=rows, names=names)


# Same day: births before marriages before deaths reads naturally; then by type name.
TYPE_WEIGHT = {"birth": 0, "baptism": 1, "death": 8, "burial": 9}


def _same_day_key(r: FactRow) -> tuple[int, str, str]:
    return TYPE_WEIGHT.get(r.type, 5), r.type, str(r.id)


def in_date_order(rows: Iterable[FactRow]) -> list[FactRow]:
    return sorted(rows, key=lambda r: (r.sort or dt.date.max, *_same_day_key(r)))


# --- Timeline -----------------------------------------------------------------------------


async def timeline(
    session: AsyncSession,
    tree_id: uuid.UUID,
    *,
    types: list[str] | None = None,
    person_id: uuid.UUID | None = None,
    from_year: int | None = None,
    to_year: int | None = None,
    limit: int = 100,
    offset: int = 0,
    hidden: Collection[uuid.UUID] = (),
) -> TimelinePage:
    facts = await load_facts(session, tree_id, hidden)
    rows = [
        r
        for r in facts.rows
        if (not types or r.type in types) and (person_id is None or r.involves(person_id))
    ]
    dated = [
        r
        for r in rows
        if r.sort is not None
        and (from_year is None or r.sort.year >= from_year)
        and (to_year is None or r.sort.year <= to_year)
    ]
    ordered = in_date_order(dated)
    return TimelinePage(
        items=[facts.out(r) for r in ordered[offset : offset + limit]],
        total=len(ordered),
        limit=limit,
        offset=offset,
        undated=sum(r.sort is None for r in rows),
    )


# --- On this day --------------------------------------------------------------------------


def exactly_dated(r: FactRow) -> bool:
    """Day, month and year are known: only such facts have anniversaries."""
    d = r.date
    return d.precision == DatePrecision.exact and bool(d.year and d.month and d.day)


def _calendar_day(year: int, month: int, day: int) -> dt.date:
    """The day an anniversary falls on in `year` (29 February → 28 February)."""
    return dt.date(year, month, min(day, calendar.monthrange(year, month)[1]))


async def on_this_day(
    session: AsyncSession,
    tree_id: uuid.UUID,
    start: dt.date,
    days: int = 0,
    *,
    hidden: Collection[uuid.UUID] = (),
) -> OnThisDay:
    """Anniversaries of exactly dated facts on `start` and the following `days` days."""
    days = max(0, min(days, MAX_WINDOW_DAYS))
    facts = await load_facts(session, tree_id, hidden)
    end = start + dt.timedelta(days=days)
    found: list[tuple[dt.date, FactRow]] = []
    for r in facts.rows:
        d = r.date
        if not exactly_dated(r) or not (d.year and d.month and d.day):
            continue
        for year in {start.year, end.year}:
            on = _calendar_day(year, d.month, d.day)
            if start <= on <= end and year > d.year:
                found.append((on, r))
    found.sort(key=lambda x: (x[0], *_same_day_key(x[1])))
    return OnThisDay(
        start=start,
        days=days,
        items=[
            Anniversary(on=on, years=on.year - (r.date.year or on.year), fact=facts.out(r))
            for on, r in found
        ],
    )


# --- Map ----------------------------------------------------------------------------------


async def map_data(
    session: AsyncSession,
    tree_id: uuid.UUID,
    person_id: uuid.UUID | None = None,
    *,
    hidden: Collection[uuid.UUID] = (),
) -> MapData:
    facts = await load_facts(session, tree_id, hidden)
    rows = [r for r in facts.rows if person_id is None or r.involves(person_id)]
    points: dict[tuple[Decimal, Decimal], MapPoint] = {}
    missing: dict[uuid.UUID, Place] = {}
    unplaced = 0
    for r in in_date_order(rows):
        if r.latitude is not None and r.longitude is not None:
            lat, lon = r.latitude, r.longitude
            label = r.cemetery_name or (r.place.name if r.place else "")
            place_id = r.place.id if r.place else None
        elif r.place and r.place.latitude is not None and r.place.longitude is not None:
            lat, lon = r.place.latitude, r.place.longitude
            label, place_id = r.place.name, r.place.id
        else:
            if r.place:
                unplaced += 1
                missing[r.place.id] = r.place
            continue
        key = (round(lat, 5), round(lon, 5))
        point = points.get(key)
        if point is None:
            point = points[key] = MapPoint(
                latitude=lat, longitude=lon, label=label, place_id=place_id, facts=[]
            )
        point.facts.append(facts.out(r))
    return MapData(
        points=list(points.values()),
        unplaced=unplaced,
        places_without_coordinates=[
            PlaceSummary.model_validate(p) for p in sorted(missing.values(), key=lambda p: p.name)
        ],
    )
