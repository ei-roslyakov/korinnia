"""Tree statistics: people, generations, notable ancestors, surnames, births by decade."""

from __future__ import annotations

import uuid
from collections import Counter, defaultdict
from collections.abc import Iterable

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dates import PartialDate, years_between
from app.models import (
    DatePrecision,
    Event,
    Gender,
    MediaFile,
    Partnership,
    Person,
    PersonName,
    Place,
    Source,
    Story,
    StoryStatus,
)
from app.schemas.insights import DecadeCount, NameCount, PersonFigure, TreeStats
from app.services.genealogy.facts import load_facts
from app.services.genealogy.kinship import FamilyIndex, load_index
from app.services.genealogy.summaries import load_names, summary_map
from app.services.genealogy.vitals import load_vitals
from app.services.search_text import strip_accents, transliterate_uk

TOP_FIRST_NAMES = 15
# Dates precise enough to compute an age from.
AGE_PRECISIONS = (DatePrecision.exact, DatePrecision.month, DatePrecision.year)
MAX_PLAUSIBLE_AGE = 125


def generations(idx: FamilyIndex, persons: Iterable[uuid.UUID]) -> int:
    """Length (in people) of the longest parent → child line."""
    ids = set(persons)
    if not ids:
        return 0
    depth: dict[uuid.UUID, int] = {}
    # Iterative post-order DFS: depth(p) = 1 + max(depth(child)).
    for root in ids:
        if root in depth:
            continue
        stack: list[tuple[uuid.UUID, bool]] = [(root, False)]
        on_stack: set[uuid.UUID] = set()
        while stack:
            node, expanded = stack.pop()
            if expanded:
                on_stack.discard(node)
                kids = [c for c in idx.children.get(node, []) if c in ids]
                depth[node] = 1 + max((depth.get(c, 0) for c in kids), default=0)
                continue
            if node in depth or node in on_stack:
                continue  # done, or a cycle in bad data
            on_stack.add(node)
            stack.append((node, True))
            stack.extend((c, False) for c in idx.children.get(node, []) if c in ids)
    return max(depth.values())


def age(birth: PartialDate | None, death: PartialDate | None) -> int | None:
    if not birth or not death or birth.precision not in AGE_PRECISIONS:
        return None
    if death.precision not in AGE_PRECISIONS or birth.year is None or death.year is None:
        return None
    if birth.precision == DatePrecision.exact and death.precision == DatePrecision.exact:
        b, d = birth.sort_key(), death.sort_key()
        if b is None or d is None:  # pragma: no cover - exact dates always have a key
            return None
        years = years_between(b, d)
    else:
        years = death.year - birth.year
    return years if 0 <= years <= MAX_PLAUSIBLE_AGE else None


def surname_key(name: str) -> str:
    """Spellings in different scripts group together: Коваленко = Kovalenko."""
    return strip_accents(transliterate_uk(name.strip())).lower()


def count_names(per_person: dict[uuid.UUID, set[str]]) -> list[NameCount]:
    """Group spellings by transliteration; count each person once per group."""
    people: dict[str, set[uuid.UUID]] = defaultdict(set)
    spellings: dict[str, Counter[str]] = defaultdict(Counter)
    for pid, names in per_person.items():
        for name in names:
            key = surname_key(name)
            if not key:
                continue
            people[key].add(pid)
            spellings[key][name.strip()] += 1
    out = []
    for key, pids in people.items():
        ranked = sorted(spellings[key].items(), key=lambda kv: (-kv[1], kv[0]))
        out.append(
            NameCount(name=ranked[0][0], count=len(pids), variants=[s for s, _ in ranked[1:]])
        )
    return sorted(out, key=lambda n: (-n.count, n.name))


async def _count(session: AsyncSession, model: type, tree_id: uuid.UUID, *extra: object) -> int:
    stmt = (
        select(func.count())
        .select_from(model)
        .where(
            model.tree_id == tree_id,  # type: ignore[attr-defined]
            model.deleted_at.is_(None),  # type: ignore[attr-defined]
            *extra,  # type: ignore[arg-type]
        )
    )
    return await session.scalar(stmt) or 0


async def tree_stats(session: AsyncSession, tree_id: uuid.UUID) -> TreeStats:
    persons = list(
        await session.scalars(
            select(Person).where(Person.tree_id == tree_id, Person.deleted_at.is_(None))
        )
    )
    live = {p.id for p in persons}
    names = await load_names(session, None, tree_id)
    vitals = await load_vitals(session, tree_id)
    idx = await load_index(session, tree_id)
    facts = await load_facts(session, tree_id)

    surnames: dict[uuid.UUID, set[str]] = {}
    first_names: dict[uuid.UUID, set[str]] = {}
    for pid in live:
        pn: list[PersonName] = names.get(pid, [])
        surnames[pid] = {n for x in pn for n in (x.last_name, x.maiden_name) if n}
        first_names[pid] = {x.first_name for x in pn if x.first_name}

    births = {pid: v.birth_date for pid, v in vitals.items() if pid in live and v.birth_date}
    deaths = {pid: v.death_date for pid, v in vitals.items() if pid in live and v.death_date}

    dated_births = [(d.sort_key(), pid) for pid, d in births.items() if d.sort_key()]
    oldest = min(dated_births, key=lambda x: (x[0], str(x[1])), default=None)

    ages = {pid: a for pid in live if (a := age(births.get(pid), deaths.get(pid))) is not None}
    longest = max(ages.items(), key=lambda kv: (kv[1], str(kv[0])), default=None)

    decades: dict[int, list[int]] = defaultdict(lambda: [0, 0])
    for i, dates in enumerate((births, deaths)):
        for d in dates.values():
            key = d.sort_key()
            if key:
                decades[key.year // 10 * 10][i] += 1

    years = [r.sort.year for r in facts.rows if r.sort]
    figures = await summary_map(
        session, tree_id, [x for x in (oldest and oldest[1], longest and longest[0]) if x]
    )
    gender = Counter(p.gender for p in persons)
    return TreeStats(
        persons=len(persons),
        male=gender[Gender.male],
        female=gender[Gender.female],
        other_gender=len(persons) - gender[Gender.male] - gender[Gender.female],
        living=sum(p.is_living for p in persons),
        deceased=sum(not p.is_living for p in persons),
        generations=generations(idx, live),
        partnerships=await _count(session, Partnership, tree_id),
        places=await _count(session, Place, tree_id),
        events=await _count(session, Event, tree_id),
        media=await _count(session, MediaFile, tree_id),
        sources=await _count(session, Source, tree_id),
        stories=await _count(session, Story, tree_id, Story.status == StoryStatus.published),
        earliest_year=min(years, default=None),
        latest_year=max(years, default=None),
        oldest_ancestor=PersonFigure(person=figures[oldest[1]]) if oldest else None,
        longest_lived=(
            PersonFigure(person=figures[longest[0]], years=longest[1]) if longest else None
        ),
        average_lifespan=round(sum(ages.values()) / len(ages), 1) if ages else None,
        lifespan_sample=len(ages),
        surnames=count_names(surnames),
        first_names=count_names(first_names)[:TOP_FIRST_NAMES],
        by_decade=[
            DecadeCount(decade=k, births=b, deaths=d) for k, (b, d) in sorted(decades.items())
        ],
    )
