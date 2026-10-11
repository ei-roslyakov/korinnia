"""A large synthetic family tree for performance testing: `python -m app.perf` (or
`make perf-tree`).

Builds a realistic shape quickly, writing rows directly (the services would audit and
snapshot every person, which takes minutes for thousands): several founding couples around
1800, 2–5 children per couple, most children marrying someone from outside the family (so
there are many roots, like a real GEDCOM), about nine generations up to today, births,
deaths and places. Deterministic: the same `--seed` gives the same tree.
"""

from __future__ import annotations

import argparse
import asyncio
import random
import sys
import time
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.dates import PartialDate
from app.core.db import get_engine, get_sessionmaker
from app.core.enums import (
    DatePrecision,
    EventType,
    Gender,
    ParentChildType,
    ParticipantRole,
    PartnershipType,
)
from app.core.logging import configure_logging
from app.models import (
    Event,
    EventParticipant,
    ParentChild,
    Partnership,
    Person,
    Place,
    Tree,
    User,
)
from app.services import trees as tree_service
from app.services.context import Actor
from app.services.genealogy.common import set_date
from app.services.genealogy.persons import presume_living
from app.services.genealogy.snapshots import make_names
from app.services.search_text import build_search_text

MALE = [
    "Іван",
    "Петро",
    "Степан",
    "Михайло",
    "Василь",
    "Григорій",
    "Олександр",
    "Микола",
    "Андрій",
    "Юрій",
    "Тарас",
    "Богдан",
    "Остап",
    "Федір",
    "Йосип",
    "Дмитро",
    "Роман",
    "Сергій",
    "Максим",
    "Ігор",
]
FEMALE = [
    "Марія",
    "Ганна",
    "Олена",
    "Параска",
    "Катерина",
    "Галина",
    "Ольга",
    "Ніна",
    "Тетяна",
    "Людмила",
    "Оксана",
    "Ірина",
    "Наталія",
    "Софія",
    "Дарина",
    "Юлія",
    "Віра",
    "Зоя",
    "Лариса",
    "Уляна",
]
SURNAMES = [
    "Коваленко",
    "Шевченко",
    "Бондаренко",
    "Ткаченко",
    "Мельник",
    "Кравченко",
    "Олійник",
    "Шевчук",
    "Поліщук",
    "Бойко",
    "Ткачук",
    "Савченко",
    "Руденко",
    "Гнатюк",
    "Мороз",
    "Литвиненко",
    "Романенко",
    "Гончаренко",
    "Лисенко",
    "Марченко",
]
PLACES = [
    ("Полтава", "Полтавська область"),
    ("Київ", None),
    ("Львів", "Львівська область"),
    ("Харків", "Харківська область"),
    ("Чернігів", "Чернігівська область"),
    ("Вінниця", "Вінницька область"),
    ("Житомир", "Житомирська область"),
    ("Коломия", "Івано-Франківська область"),
    ("Миргород", "Полтавська область"),
    ("Дніпро", "Дніпропетровська область"),
]
PATRONYMIC_STEM = {
    "Іван": "Іван",
    "Петро": "Петр",
    "Степан": "Степан",
    "Михайло": "Михайл",
    "Василь": "Василь",
    "Григорій": "Григор",
    "Олександр": "Олександр",
    "Микола": "Миколай",
    "Андрій": "Андрій",
    "Юрій": "Юрій",
    "Тарас": "Тарас",
    "Богдан": "Богдан",
    "Остап": "Остап",
    "Федір": "Федор",
    "Йосип": "Йосип",
    "Дмитро": "Дмитр",
    "Роман": "Роман",
    "Сергій": "Сергій",
    "Максим": "Максим",
    "Ігор": "Ігор",
}
THIS_YEAR = 2026


@dataclass
class _P:
    id: uuid.UUID
    gender: Gender
    first: str
    last: str
    patronymic: str | None
    maiden: str | None
    born: int
    died: int | None


def _patronymic(father: str, gender: Gender) -> str:
    stem = PATRONYMIC_STEM[father]
    if stem.endswith(("й", "ь")):
        stem = stem[:-1]
        return stem + ("йович" if gender == Gender.male else "ївна")
    return stem + ("ович" if gender == Gender.male else "івна")


async def build(
    session: AsyncSession, owner: User, *, people: int, seed: int = 1, name: str | None = None
) -> Tree:
    """Create a tree with exactly `people` people (see the module docstring)."""
    rnd = random.Random(seed)  # noqa: S311 (test data, not security)
    tree = await tree_service.create_tree(
        session,
        name=name or f"Великий родовід (тест, {people})",
        description="Синтетичний родовід для перевірки швидкодії.",
        owner=owner,
        actor=Actor(owner, ip="perf"),
    )
    places = []
    for place_name, region in PLACES:
        place = Place(
            id=uuid.uuid4(),
            tree_id=tree.id,
            name=place_name,
            region=region,
            country="Україна",
            historical_names=[],
        )
        place.search_text = build_search_text([place_name])
        session.add(place)
        places.append(place.id)

    persons: list[_P] = []

    def new_person(
        gender: Gender, born: int, last: str, father: str | None = None, maiden: str | None = None
    ) -> _P:
        first = rnd.choice(MALE if gender == Gender.male else FEMALE)
        died = None
        if born < 1945 or rnd.random() < 0.1:
            died = min(THIS_YEAR, born + rnd.randint(35, 92))
        p = _P(
            uuid.uuid4(),
            gender,
            first,
            last,
            _patronymic(father, gender) if father else None,
            maiden,
            born,
            died,
        )
        persons.append(p)
        return p

    couples: list[tuple[_P, _P | None]] = []
    links: list[tuple[uuid.UUID, uuid.UUID]] = []
    founders = max(2, people // 250)
    generation: list[tuple[_P, _P | None]] = []
    for _ in range(founders):
        surname = rnd.choice(SURNAMES)
        husband = new_person(Gender.male, rnd.randint(1790, 1810), surname)
        wife = new_person(
            Gender.female, husband.born + rnd.randint(-5, 3), surname, maiden=rnd.choice(SURNAMES)
        )
        generation.append((husband, wife))
    couples += generation
    while len(persons) < people and generation:
        nxt: list[tuple[_P, _P | None]] = []
        for father, mother in generation:
            if len(persons) >= people:
                break
            base = max(father.born, mother.born if mother else father.born)
            for _ in range(rnd.choice([1, 2, 2, 3, 3, 4, 5])):
                if len(persons) >= people:
                    break
                born = base + rnd.randint(20, 36)
                if born > THIS_YEAR - 1:
                    break
                gender = rnd.choice([Gender.male, Gender.female])
                # A patronymic comes from the father (none for a single mother's child).
                dad = father.first if father.gender == Gender.male else None
                child = new_person(gender, born, father.last, father=dad)
                links.append((father.id, child.id))
                if mother:
                    links.append((mother.id, child.id))
                # Most grow up and marry someone from another family.
                if born < THIS_YEAR - 25 and rnd.random() < 0.8 and len(persons) < people:
                    other = Gender.female if gender == Gender.male else Gender.male
                    spouse_last = rnd.choice(SURNAMES)
                    spouse = new_person(
                        other,
                        born + rnd.randint(-4, 4),
                        father.last if other == Gender.female else spouse_last,
                        maiden=spouse_last if other == Gender.female else None,
                    )
                    couple = (child, spouse) if gender == Gender.male else (spouse, child)
                    if gender == Gender.female:
                        child.last = spouse.last
                        child.maiden = father.last
                    couples.append(couple)
                    nxt.append(couple)
                elif born < THIS_YEAR - 25 and rnd.random() < 0.3:
                    nxt.append((child, None))  # a single parent
        generation = nxt

    for p in persons:
        birth = PartialDate(year=p.born, precision=DatePrecision.year)
        person = Person(
            id=p.id,
            tree_id=tree.id,
            gender=p.gender,
            is_living=presume_living(birth, p.died is not None),
        )
        names = [
            {
                "first_name": p.first,
                "patronymic": p.patronymic,
                "last_name": p.last,
                "maiden_name": p.maiden,
                "type": "married" if p.maiden else "birth",
            }
        ]
        person.names = make_names(person, names)
        session.add(person)
        for kind, year in ((EventType.birth, p.born), (EventType.death, p.died)):
            if year is None:
                continue
            event = Event(id=uuid.uuid4(), tree_id=tree.id, type=kind, place_id=rnd.choice(places))
            set_date(
                event, "date", "date_sort", PartialDate(year=year, precision=DatePrecision.year)
            )
            event.participants = [EventParticipant(person_id=p.id, role=ParticipantRole.principal)]
            session.add(event)
    await session.flush()
    for parent_id, child_id in links:
        session.add(
            ParentChild(
                id=uuid.uuid4(),
                tree_id=tree.id,
                parent_id=parent_id,
                child_id=child_id,
                type=ParentChildType.biological,
            )
        )
    for a, b in couples:
        if b is None:
            continue
        partnership = Partnership(
            id=uuid.uuid4(),
            tree_id=tree.id,
            person_a_id=a.id,
            person_b_id=b.id,
            type=PartnershipType.marriage,
        )
        set_date(
            partnership,
            "start_date",
            "start_sort",
            PartialDate(year=max(a.born, b.born) + 20, precision=DatePrecision.year),
        )
        set_date(partnership, "end_date", "end_sort", PartialDate())
        session.add(partnership)
    await session.commit()
    return tree


async def run(args: argparse.Namespace) -> int:
    try:
        async with get_sessionmaker()() as session:
            query = select(User).where(User.is_active.is_(True))
            query = (
                query.where(User.email == args.owner.lower())
                if args.owner
                else query.where(User.is_superadmin.is_(True))
            )
            owner = (await session.scalars(query.order_by(User.created_at))).first()
            if owner is None:
                print("no owner found", file=sys.stderr)
                return 1
            started = time.perf_counter()
            tree = await build(session, owner, people=args.people, seed=args.seed)
            print(
                f"perf: created {tree.name!r} ({tree.id}) with {args.people} people "
                f"for {owner.email} in {time.perf_counter() - started:.1f} s"
            )
            return 0
    finally:
        await get_engine().dispose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.perf",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--people", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--owner", help="email of the tree owner (default: first superadmin)")
    args = parser.parse_args(argv)
    configure_logging(get_settings().log_level)
    return asyncio.run(run(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
