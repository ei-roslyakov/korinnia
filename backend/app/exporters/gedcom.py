"""GEDCOM 5.5.1 export (UTF-8) of one tree: people, names, life events, places, families,
sources and citations. The counterpart of `app/importers/gedcom`; files exported here read
back into Korinnia (and other programs) with the same people, dates and links.

Not included: media files (a .ged file holds text only), comments, stories, history.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dates import PartialDate
from app.core.enums import (
    CitationQuality,
    DatePrecision,
    EventType,
    Gender,
    NameType,
    ParentChildType,
    ParticipantRole,
    PartnershipEndReason,
    PartnershipType,
)
from app.models import (
    Citation,
    Event,
    EventParticipant,
    ParentChild,
    Partnership,
    Person,
    PersonName,
    Place,
    Source,
    Tree,
)

_MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
# Our event types → GEDCOM tags (None: a generic EVEN with a TYPE).
_EVENT_TAGS: dict[EventType, str | None] = {
    EventType.birth: "BIRT",
    EventType.baptism: "BAPM",
    EventType.death: "DEAT",
    EventType.burial: "BURI",
    EventType.education: "EDUC",
    EventType.graduation: "GRAD",
    EventType.military_service: "_MILT",
    EventType.occupation: "OCCU",
    EventType.residence: "RESI",
    EventType.emigration: "EMIG",
    EventType.immigration: "IMMI",
    EventType.award: None,
    EventType.illness: None,
    EventType.custom: None,
}
# Tags whose value is the event's title (an occupation, a school).
_VALUE_TAGS = {"OCCU", "EDUC", "GRAD"}
_EVEN_TYPES = {EventType.award: "Award", EventType.illness: "Illness"}
_NAME_TYPES = {
    NameType.married: "married",
    NameType.nickname: "nickname",
    NameType.alias: "aka",
    NameType.religious: "aka",
    NameType.other: "aka",
}
_PEDI = {
    ParentChildType.adoptive: "adopted",
    ParentChildType.foster: "foster",
    ParentChildType.step: "step",
}
_QUAY = {
    CitationQuality.primary: "3",
    CitationQuality.secondary: "2",
    CitationQuality.family_tradition: "1",
    CitationQuality.unverified: "0",
}
MAX_LINE = 240  # value characters per line before CONC (the standard allows 255 per line)


# --- Formatting ---------------------------------------------------------------------------


def _ymd(y: int, m: int | None, d: int | None) -> str:
    return " ".join(str(x) for x in (d, _MONTHS[m - 1] if m else None, y) if x)


def gedcom_date(d: PartialDate | None) -> str | None:
    """A partial date in GEDCOM form ("ABT 1850", "BET 1914 AND 1918", "(at Easter)")."""
    if d is None or d.is_empty:
        return None
    phrase = (d.phrase or "").replace("(", "[").replace(")", "]").strip()
    if d.year is None:
        return f"({phrase})" if phrase else None
    base = _ymd(d.year, d.month, d.day)
    match d.precision:
        case DatePrecision.approx:
            text = f"ABT {base}"
        case DatePrecision.before:
            text = f"BEF {base}"
        case DatePrecision.after:
            text = f"AFT {base}"
        case DatePrecision.between if d.end_year is not None:
            text = f"BET {base} AND {_ymd(d.end_year, d.end_month, d.end_day)}"
        case _:
            text = base
    return f"INT {text} ({phrase})" if phrase else text


def _coordinate(value: Decimal, positive: str, negative: str) -> str:
    v = value.normalize()
    return f"{negative if v < 0 else positive}{abs(v)}"


class _Lines:
    def __init__(self) -> None:
        self.out: list[str] = []

    def add(self, level: int, tag: str, value: str | None = None, xref: str | None = None) -> None:
        """One line; long or multi-line values continue with CONC / CONT; '@' is escaped."""
        head = f"{level} {xref + ' ' if xref else ''}{tag}"
        if value is None or value == "":
            self.out.append(head)
            return
        text = value.replace("\r\n", "\n").replace("\r", "\n")
        if not (value.startswith("@") and value.endswith("@") and " " not in value):
            text = text.replace("@", "@@")  # not a pointer
        first = True
        for para in text.split("\n"):
            chunks = [para[j : j + MAX_LINE] for j in range(0, len(para), MAX_LINE)] or [""]
            for k, chunk in enumerate(chunks):
                if first:
                    self.out.append(f"{head} {chunk}".rstrip() if chunk else head)
                    first = False
                elif k == 0:
                    self.out.append(f"{level + 1} CONT {chunk}".rstrip())
                else:
                    self.out.append(f"{level + 1} CONC {chunk}")

    def text(self) -> str:
        return "\n".join(self.out) + "\n"


# --- Loading --------------------------------------------------------------------------------


@dataclass
class _Family:
    parents: tuple[uuid.UUID, ...]
    children: list[uuid.UUID] = field(default_factory=list)
    partnership: Partnership | None = None


@dataclass
class _Data:
    persons: list[Person]
    names: dict[uuid.UUID, list[PersonName]]
    events: dict[uuid.UUID, list[Event]]
    links: list[ParentChild]
    partnerships: list[Partnership]
    places: dict[uuid.UUID, Place]
    sources: list[Source]
    citations: dict[tuple[str, uuid.UUID], list[Citation]]


async def _load(session: AsyncSession, tree_id: uuid.UUID) -> _Data:
    live = Person.deleted_at.is_(None)
    persons = list(await session.scalars(select(Person).where(Person.tree_id == tree_id, live)))
    ids = {p.id for p in persons}
    names: dict[uuid.UUID, list[PersonName]] = defaultdict(list)
    for n in await session.scalars(
        select(PersonName)
        .where(PersonName.person_id.in_(ids))
        .order_by(PersonName.is_primary.desc(), PersonName.sort_order)
    ):
        names[n.person_id].append(n)
    events: dict[uuid.UUID, list[Event]] = defaultdict(list)
    rows = await session.execute(
        select(EventParticipant.person_id, Event)
        .join(Event, Event.id == EventParticipant.event_id)
        .where(
            Event.tree_id == tree_id,
            Event.deleted_at.is_(None),
            EventParticipant.role == ParticipantRole.principal,
            EventParticipant.person_id.in_(ids),
        )
        .order_by(Event.date_sort.nulls_last(), Event.created_at)
    )
    for person_id, event in rows:
        events[person_id].append(event)
    links = [
        link
        for link in await session.scalars(
            select(ParentChild).where(
                ParentChild.tree_id == tree_id, ParentChild.deleted_at.is_(None)
            )
        )
        if link.parent_id in ids and link.child_id in ids
    ]
    partnerships = [
        p
        for p in await session.scalars(
            select(Partnership).where(
                Partnership.tree_id == tree_id, Partnership.deleted_at.is_(None)
            )
        )
        if p.person_a_id in ids and p.person_b_id in ids
    ]
    places = {
        p.id: p
        for p in await session.scalars(
            select(Place).where(Place.tree_id == tree_id, Place.deleted_at.is_(None))
        )
    }
    sources = list(
        await session.scalars(
            select(Source)
            .where(Source.tree_id == tree_id, Source.deleted_at.is_(None))
            .order_by(Source.created_at)
        )
    )
    citations: dict[tuple[str, uuid.UUID], list[Citation]] = defaultdict(list)
    for c in await session.scalars(
        select(Citation)
        .where(Citation.tree_id == tree_id, Citation.deleted_at.is_(None))
        .order_by(Citation.created_at)
    ):
        kind = "person" if c.entity_type.value in ("person", "person_name") else c.entity_type.value
        citations[(kind, c.entity_id)].append(c)
    return _Data(persons, names, events, links, partnerships, places, sources, citations)


def _families(data: _Data) -> list[_Family]:
    """Couples and their children: one family per set of parents (a child's parents form one
    family), plus couples without children."""
    parents_of: dict[uuid.UUID, list[uuid.UUID]] = defaultdict(list)
    for link in data.links:
        parents_of[link.child_id].append(link.parent_id)
    pair = {frozenset((p.person_a_id, p.person_b_id)): p for p in data.partnerships}
    families: dict[frozenset[uuid.UUID], _Family] = {}
    for child, parents in parents_of.items():
        key = frozenset(parents[:2])
        fam = families.setdefault(
            key, _Family(parents=tuple(parents[:2]), partnership=pair.get(key))
        )
        fam.children.append(child)
    for key, p in pair.items():
        families.setdefault(key, _Family(parents=(p.person_a_id, p.person_b_id), partnership=p))
    return list(families.values())


# --- Writing --------------------------------------------------------------------------------


def _place_text(place: Place) -> str:
    return ", ".join(x for x in (place.name, place.region, place.country) if x)


async def export_tree(
    session: AsyncSession,
    tree: Tree,
    *,
    hide_living: bool = False,
    app_version: str = "dev",
    submitter: str | None = None,
    today: date | None = None,
) -> str:
    data = await _load(session, tree.id)
    today = today or date.today()
    persons = sorted(
        data.persons,
        key=lambda p: (
            min((e.date_sort for e in data.events[p.id] if e.date_sort), default=date.max),
            p.created_at,
        ),
    )
    pid = {p.id: f"@I{i}@" for i, p in enumerate(persons, start=1)}
    families = _families(data)
    fid = {id(f): f"@F{i}@" for i, f in enumerate(families, start=1)}
    sid = {s.id: f"@S{i}@" for i, s in enumerate(data.sources, start=1)}
    repos = sorted({s.archive_name for s in data.sources if s.archive_name})
    rid = {name: f"@R{i}@" for i, name in enumerate(repos, start=1)}
    private = {p.id for p in persons if hide_living and p.is_living}
    # Lookups for the family links of each person (avoid scanning all families per person).
    child_in: dict[uuid.UUID, list[_Family]] = defaultdict(list)
    parent_in: dict[uuid.UUID, list[_Family]] = defaultdict(list)
    for f in families:
        for c in f.children:
            child_in[c].append(f)
        for parent in f.parents:
            parent_in[parent].append(f)
    link_type = {(link.parent_id, link.child_id): link.type for link in data.links}

    w = _Lines()
    w.add(0, "HEAD")
    w.add(1, "SOUR", "KORINNIA")
    w.add(2, "NAME", "Korinnia")
    w.add(2, "VERS", app_version)
    w.add(1, "DATE", _ymd(today.year, today.month, today.day))
    w.add(1, "SUBM", "@SUB1@")
    w.add(1, "FILE", tree.name)
    w.add(1, "GEDC")
    w.add(2, "VERS", "5.5.1")
    w.add(2, "FORM", "LINEAGE-LINKED")
    w.add(1, "CHAR", "UTF-8")
    w.add(0, "SUBM", xref="@SUB1@")
    w.add(1, "NAME", submitter or "Korinnia")

    def cite(level: int, kind: str, entity_id: uuid.UUID) -> None:
        for c in data.citations.get((kind, entity_id), []):
            if c.source_id not in sid:
                continue
            w.add(level, "SOUR", sid[c.source_id])
            if c.page:
                w.add(level + 1, "PAGE", c.page)
            if c.notes:
                w.add(level + 1, "NOTE", c.notes)
            w.add(level + 1, "QUAY", _QUAY.get(c.quality, "0"))

    def place(
        level: int, place_id: uuid.UUID | None, lat: Decimal | None, lon: Decimal | None
    ) -> None:
        p = data.places.get(place_id) if place_id else None
        if p is None and lat is None:
            return
        w.add(level, "PLAC", _place_text(p) if p else "")
        lat = lat if lat is not None else (p.latitude if p else None)
        lon = lon if lon is not None else (p.longitude if p else None)
        if lat is not None and lon is not None:
            w.add(level + 1, "MAP")
            w.add(level + 2, "LATI", _coordinate(lat, "N", "S"))
            w.add(level + 2, "LONG", _coordinate(lon, "E", "W"))

    def event(e: Event) -> None:
        tag = _EVENT_TAGS.get(e.type)
        if tag is None:
            w.add(1, "EVEN")
            w.add(2, "TYPE", e.title or _EVEN_TYPES.get(e.type, "Event"))
        elif tag in _VALUE_TAGS:
            w.add(1, tag, e.title)
        else:
            w.add(1, tag, None if (e.date_sort or e.place_id) else "Y")
            if e.title and tag not in ("BIRT", "DEAT"):
                w.add(2, "TYPE", e.title)
        if d := gedcom_date(e.date):
            w.add(2, "DATE", d)
        place(2, e.place_id, e.latitude, e.longitude)
        if e.cemetery_name or e.burial_plot:
            w.add(2, "ADDR", ", ".join(x for x in (e.cemetery_name, e.burial_plot) if x))
        if e.description:
            w.add(2, "NOTE", e.description)
        cite(2, "event", e.id)

    for p in persons:
        w.add(0, "INDI", xref=pid[p.id])
        names = data.names.get(p.id, [])
        if p.id in private:
            surname = next((n.last_name for n in names if n.last_name), "")
            w.add(1, "NAME", f"Living /{surname}/")
        for n in [] if p.id in private else names:
            given = " ".join(x for x in (n.first_name, n.middle_name, n.patronymic) if x)
            w.add(1, "NAME", f"{given} /{n.last_name or ''}/".strip())
            if given:
                w.add(2, "GIVN", given)
            if n.last_name:
                w.add(2, "SURN", n.last_name)
            if n.type in _NAME_TYPES:
                w.add(2, "TYPE", _NAME_TYPES[n.type])
            if n.maiden_name and n.maiden_name != n.last_name:
                maiden = f"{given} /{n.maiden_name}/".strip()
                if not any(m.last_name == n.maiden_name for m in names):
                    w.add(1, "NAME", maiden)
                    if given:
                        w.add(2, "GIVN", given)
                    w.add(2, "SURN", n.maiden_name)
                    w.add(2, "TYPE", "birth")
        w.add(1, "SEX", {Gender.male: "M", Gender.female: "F"}.get(p.gender, "U"))
        if p.id not in private:
            for e in data.events.get(p.id, []):
                event(e)
            if p.occupation and not any(
                e.type == EventType.occupation for e in data.events.get(p.id, [])
            ):
                w.add(1, "OCCU", p.occupation)
            if p.education:
                w.add(1, "EDUC", p.education)
            if p.religion:
                w.add(1, "RELI", p.religion)
            if p.nationality:
                w.add(1, "NATI", p.nationality)
            for text in (p.short_summary, p.biography, p.notes_for_descendants):
                if text:
                    w.add(1, "NOTE", text)
            cite(1, "person", p.id)
            for n in names:
                cite(1, "person", n.id)
        for f in child_in.get(p.id, []):
            w.add(1, "FAMC", fid[id(f)])
            kinds = {link_type[(parent, p.id)] for parent in f.parents}
            kind = next((_PEDI[k] for k in kinds if k in _PEDI), None)
            if kind:
                w.add(2, "PEDI", kind)
        for f in parent_in.get(p.id, []):
            w.add(1, "FAMS", fid[id(f)])

    gender = {p.id: p.gender for p in persons}
    for f in families:
        w.add(0, "FAM", xref=fid[id(f)])
        a: uuid.UUID | None = f.parents[0] if f.parents else None
        b: uuid.UUID | None = f.parents[1] if len(f.parents) > 1 else None
        # HUSB is the male partner where genders say so; otherwise the first.
        if a and b and gender.get(a) == Gender.female and gender.get(b) != Gender.female:
            a, b = b, a
        if a is not None:
            w.add(1, "HUSB", pid[a])
        if b is not None:
            w.add(1, "WIFE", pid[b])
        for child in sorted(f.children, key=lambda c: pid[c]):
            w.add(1, "CHIL", pid[child])
        ps = f.partnership
        hidden = ps is not None and any(x in private for x in f.parents)
        if ps is not None and not hidden:
            if ps.type == PartnershipType.marriage:
                dated = ps.start_date is not None and not ps.start_date.is_empty
                w.add(1, "MARR", None if dated or ps.place_id else "Y")
                if d := gedcom_date(ps.start_date):
                    w.add(2, "DATE", d)
                place(2, ps.place_id, None, None)
                cite(2, "partnership", ps.id)
            if ps.end_reason == PartnershipEndReason.divorce:
                w.add(1, "DIV", None if ps.end_date and not ps.end_date.is_empty else "Y")
                if d := gedcom_date(ps.end_date):
                    w.add(2, "DATE", d)
            elif ps.end_reason == PartnershipEndReason.separation:
                w.add(1, "_SEPR", None if ps.end_date and not ps.end_date.is_empty else "Y")
                if d := gedcom_date(ps.end_date):
                    w.add(2, "DATE", d)
            if ps.notes:
                w.add(1, "NOTE", ps.notes)
            if ps.type != PartnershipType.marriage:
                cite(1, "partnership", ps.id)

    for s in data.sources:
        w.add(0, "SOUR", xref=sid[s.id])
        w.add(1, "TITL", s.title)
        if s.author:
            w.add(1, "AUTH", s.author)
        if s.archive_name:
            w.add(1, "REPO", rid[s.archive_name])
            if s.reference_number:
                w.add(2, "CALN", s.reference_number)
        if s.url:
            w.add(1, "WWW", s.url)
        if s.notes:
            w.add(1, "NOTE", s.notes)
    for name, xref in rid.items():
        w.add(0, "REPO", xref=xref)
        w.add(1, "NAME", name)
    w.add(0, "TRLR")
    return w.text()
