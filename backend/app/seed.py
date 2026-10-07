"""Demo family: `python -m app.seed` (or `make seed`).

Creates the tree "Родина Коваленків (демо)" — 25 fictional people across 5 generations
(1860s–1980s) with Cyrillic and Latin names, places with historical names, life events,
burial details and an emigration to Canada. Uses the regular services, so everything is
validated and recorded in the history like a manual edit. Running it again does nothing
while the demo tree exists. Photos, sources and stories are added in later phases.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_engine, get_sessionmaker
from app.core.logging import configure_logging
from app.models import Tree, User
from app.schemas.events import EventCreate
from app.schemas.persons import PersonCreate
from app.schemas.places import PlaceCreate
from app.schemas.relationships import ParentChildCreate, PartnershipCreate
from app.services import trees as tree_service
from app.services.context import Actor
from app.services.genealogy import events as event_service
from app.services.genealogy import persons as person_service
from app.services.genealogy import places as place_service
from app.services.genealogy import relationships as rel_service

TREE_NAME = "Родина Коваленків (демо)"

PLACES: dict[str, dict[str, Any]] = {
    "sorochyntsi": {
        "name": "Великі Сорочинці",
        "region": "Полтавська область",
        "country": "Україна",
        "latitude": "50.022500",
        "longitude": "33.940600",
        "historical_names": [
            {
                "name": "Великі Сорочинці, Миргородський повіт, Полтавська губернія",
                "until_year": 1923,
            },
        ],
    },
    "poltava": {
        "name": "Полтава",
        "region": "Полтавська область",
        "country": "Україна",
        "latitude": "49.588300",
        "longitude": "34.551400",
    },
    "ivano": {
        "name": "Івано-Франківськ",
        "region": "Івано-Франківська область",
        "country": "Україна",
        "latitude": "48.922600",
        "longitude": "24.711100",
        "historical_names": [
            {"name": "Станиславів", "until_year": 1962},
            {
                "name": "Stanisławów",
                "from_year": 1919,
                "until_year": 1939,
                "note": "У складі Польщі",
            },
            {"name": "Stanislau", "until_year": 1918, "note": "Австро-Угорщина"},
        ],
    },
    "lviv": {
        "name": "Львів",
        "region": "Львівська область",
        "country": "Україна",
        "latitude": "49.839700",
        "longitude": "24.029700",
        "historical_names": [
            {"name": "Lwów", "from_year": 1919, "until_year": 1939},
            {"name": "Lemberg", "until_year": 1918},
        ],
    },
    "kharkiv": {
        "name": "Харків",
        "region": "Харківська область",
        "country": "Україна",
        "latitude": "49.993500",
        "longitude": "36.230400",
    },
    "kyiv": {
        "name": "Київ",
        "country": "Україна",
        "latitude": "50.450100",
        "longitude": "30.523400",
    },
    "toronto": {
        "name": "Toronto",
        "region": "Ontario",
        "country": "Canada",
        "latitude": "43.653200",
        "longitude": "-79.383200",
    },
}


@dataclass
class P:
    key: str
    gender: str
    first: str
    last: str
    patronymic: str | None = None
    maiden: str | None = None
    born: dict[str, Any] | None = None
    born_in: str | None = None
    died: dict[str, Any] | None = None
    died_in: str | None = None
    latin: tuple[str, str] | None = None  # (first, last) Latin spelling
    latin_primary: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


def yr(year: int, **kw: Any) -> dict[str, Any]:
    return {"year": year, **kw}


PEOPLE: list[P] = [
    # Generation 1
    P(
        "stepan",
        "male",
        "Степан",
        "Коваленко",
        born=yr(1862),
        born_in="sorochyntsi",
        died=yr(1931, month=11, day=2),
        died_in="sorochyntsi",
        latin=("Stepan", "Kovalenko"),
        extra={"occupation": "Коваль", "research_status": "partial"},
    ),
    P(
        "paraska",
        "female",
        "Параска",
        "Коваленко",
        maiden="Бойко",
        born=yr(1866, precision="approx"),
        born_in="sorochyntsi",
        died=yr(1940),
        died_in="sorochyntsi",
    ),
    # Generation 2
    P(
        "ivan",
        "male",
        "Іван",
        "Коваленко",
        "Степанович",
        born=yr(1890, month=1, day=7),
        born_in="sorochyntsi",
        died=yr(1944, precision="before"),
        latin=("Ivan", "Kovalenko"),
        extra={"occupation": "Хлібороб, згодом бригадир колгоспу"},
    ),
    P(
        "hanna",
        "female",
        "Ганна",
        "Коваленко",
        maiden="Мельник",
        born=yr(1894, precision="approx"),
        born_in="poltava",
        died=yr(1971, month=4),
        died_in="poltava",
    ),
    P(
        "mariia",
        "female",
        "Марія",
        "Ткач",
        "Степанівна",
        maiden="Коваленко",
        born=yr(1893),
        born_in="sorochyntsi",
        died=yr(1975),
        died_in="poltava",
    ),
    P("fedir", "male", "Федір", "Ткач", born=yr(1888), died=yr(1955), died_in="poltava"),
    P(
        "yosyp",
        "male",
        "Йосип",
        "Шевчук",
        born=yr(1885),
        born_in="ivano",
        died=yr(1950),
        died_in="ivano",
        latin=("Józef", "Szewczuk"),
        extra={"religion": "Греко-католик"},
    ),
    P(
        "kateryna",
        "female",
        "Катерина",
        "Шевчук",
        maiden="Гнатюк",
        born=yr(1889),
        born_in="ivano",
        died=yr(1960),
        died_in="lviv",
    ),
    # Generation 3
    P(
        "oleksandr",
        "male",
        "Олександр",
        "Коваленко",
        "Іванович",
        born=yr(1919, month=3, day=12),
        born_in="sorochyntsi",
        died=yr(1995, month=8, day=30),
        died_in="kyiv",
        latin=("Oleksandr", "Kovalenko"),
        extra={
            "occupation": "Інженер-будівельник",
            "education": "Харківський інженерно-будівельний інститут",
        },
    ),
    P(
        "halyna",
        "female",
        "Галина",
        "Коваленко",
        "Йосипівна",
        maiden="Шевчук",
        born=yr(1923, month=2, day=14),
        born_in="ivano",
        died=yr(2010, month=12, day=1),
        died_in="kyiv",
        latin=("Halyna", "Kovalenko"),
        extra={
            "occupation": "Вчителька української мови",
            "short_summary": "Вчителька, берегиня родинних історій.",
            "biography": (
                "Галина народилася 14 лютого 1923 року в Станиславові.\n\n"
                "## Війна\n\nУ 1944 році родина переїхала до Львова. "
                "Там вона закінчила педагогічні курси.\n\n"
                "## Родина\n\nУ 1946 році вийшла заміж за Олександра Коваленка; "
                "разом вони виховали двох дітей — Володимира й Тетяну."
            ),
            "notes_for_descendants": (
                "Зберігайте листи від тітки Ольги з Канади — вони в синій скриньці."
            ),
            "research_status": "complete",
        },
    ),
    P(
        "petro",
        "male",
        "Петро",
        "Коваленко",
        "Іванович",
        born=yr(1922),
        born_in="sorochyntsi",
        died=yr(1944, precision="approx"),
        extra={"short_summary": "Загинув на фронті."},
    ),
    P(
        "olha",
        "female",
        "Ольга",
        "Ткачук",
        "Йосипівна",
        maiden="Шевчук",
        born=yr(1926),
        born_in="ivano",
        died=yr(2012),
        died_in="toronto",
        latin=("Olga", "Tkachuk"),
    ),
    P(
        "mykhailo",
        "male",
        "Михайло",
        "Ткачук",
        born=yr(1924),
        born_in="lviv",
        died=yr(2001),
        died_in="toronto",
        latin=("Michael", "Tkachuk"),
    ),
    P(
        "mykola",
        "male",
        "Микола",
        "Ткач",
        "Федорович",
        born=yr(1915),
        born_in="poltava",
        died=yr(1980),
        died_in="poltava",
    ),
    # Generation 4
    P(
        "volodymyr",
        "male",
        "Володимир",
        "Коваленко",
        "Олександрович",
        born=yr(1948, month=5, day=9),
        born_in="lviv",
        died=yr(2015),
        died_in="kyiv",
        latin=("Volodymyr", "Kovalenko"),
    ),
    P(
        "liudmyla",
        "female",
        "Людмила",
        "Коваленко",
        maiden="Романенко",
        born=yr(1951),
        born_in="kharkiv",
    ),
    P(
        "tetiana",
        "female",
        "Тетяна",
        "Бондар",
        "Олександрівна",
        maiden="Коваленко",
        born=yr(1952),
        born_in="lviv",
    ),
    P("andrii_b", "male", "Андрій", "Бондар", born=yr(1950), died=yr(2020), died_in="kyiv"),
    P(
        "stephen",
        "male",
        "Степан",
        "Ткачук",
        born=yr(1952),
        born_in="toronto",
        latin=("Stephen", "Tkachuk"),
        latin_primary=True,
    ),
    # Generation 5
    P(
        "andrii",
        "male",
        "Андрій",
        "Коваленко",
        "Володимирович",
        born=yr(1975),
        born_in="kyiv",
        latin=("Andrii", "Kovalenko"),
    ),
    P("oksana", "female", "Оксана", "Коваленко", maiden="Литвин", born=yr(1978)),
    P("nataliia", "female", "Наталія", "Коваленко", "Володимирівна", born=yr(1979), born_in="kyiv"),
    P("iryna", "female", "Ірина", "Бондар", "Андріївна", born=yr(1976), born_in="kyiv"),
    P("oleh", "male", "Олег", "Бондар", "Андрійович", born=yr(1980), born_in="kyiv"),
    P(
        "emily",
        "female",
        "Emily",
        "Tkachuk",
        born=yr(1980),
        born_in="toronto",
        latin=("Emily", "Tkachuk"),
        latin_primary=True,
    ),
]

# (parents..., child)
FAMILIES: list[tuple[tuple[str, ...], list[str]]] = [
    (("stepan", "paraska"), ["ivan", "mariia"]),
    (("ivan", "hanna"), ["oleksandr", "petro"]),
    (("mariia", "fedir"), ["mykola"]),
    (("yosyp", "kateryna"), ["halyna", "olha"]),
    (("oleksandr", "halyna"), ["volodymyr", "tetiana"]),
    (("olha", "mykhailo"), ["stephen"]),
    (("volodymyr", "liudmyla"), ["andrii", "nataliia"]),
    (("tetiana", "andrii_b"), ["iryna", "oleh"]),
    (("stephen",), ["emily"]),
]

# (a, b, start, place, end, end_reason)
MARRIAGES: list[
    tuple[str, str, dict[str, Any] | None, str | None, dict[str, Any] | None, str | None]
] = [
    ("stepan", "paraska", yr(1888, precision="approx"), "sorochyntsi", yr(1931), "death"),
    ("ivan", "hanna", yr(1917, month=10), "sorochyntsi", None, None),
    ("mariia", "fedir", yr(1913), "poltava", None, None),
    ("yosyp", "kateryna", yr(1920), "ivano", None, None),
    ("oleksandr", "halyna", yr(1946, month=6, day=22), "lviv", yr(1995), "death"),
    ("olha", "mykhailo", yr(1950), "toronto", None, None),
    ("volodymyr", "liudmyla", yr(1973), "kyiv", None, None),
    ("tetiana", "andrii_b", yr(1974), "kyiv", None, None),
    ("andrii", "oksana", yr(2003, month=8, day=16), "kyiv", None, None),
]


def _names(p: P) -> list[dict[str, Any]]:
    native = {
        "first_name": p.first,
        "patronymic": p.patronymic,
        "last_name": p.last,
        "maiden_name": p.maiden,
        "type": "married" if p.maiden else "birth",
        "script": "latin" if p.latin_primary and p.latin == (p.first, p.last) else "cyrillic",
        "is_primary": not p.latin_primary,
    }
    names = [native]
    if p.maiden:
        names.append(
            {
                "first_name": p.first,
                "patronymic": p.patronymic,
                "last_name": p.maiden,
                "type": "birth",
            }
        )
    if p.latin and p.latin != (p.first, p.last):
        names.append(
            {
                "first_name": p.latin[0],
                "last_name": p.latin[1],
                "script": "latin",
                "type": "birth" if not p.maiden else "married",
                "is_primary": p.latin_primary,
            }
        )
    if p.latin_primary and p.latin == (p.first, p.last):
        native["is_primary"] = True
    return names


async def seed(session: AsyncSession, owner: User) -> Tree | None:
    if await session.scalar(select(Tree).where(Tree.name == TREE_NAME, Tree.deleted_at.is_(None))):
        return None
    actor = Actor(owner, ip="seed")
    tree = await tree_service.create_tree(
        session,
        name=TREE_NAME,
        description="Вигадана демонстраційна родина: п'ять поколінь, 1860-ті — 1980-ті.",
        owner=owner,
        actor=actor,
    )
    places = {
        key: (await place_service.create_place(session, tree.id, PlaceCreate(**data), actor)).id
        for key, data in PLACES.items()
    }
    ids: dict[str, Any] = {}
    for p in PEOPLE:
        body: dict[str, Any] = {"gender": p.gender, "names": _names(p), **p.extra}
        if p.born:
            body["birth"] = {"date": p.born, "place_id": places.get(p.born_in or "")}
        if p.died:
            body["death"] = {"date": p.died, "place_id": places.get(p.died_in or "")}
        person = await person_service.create_person(
            session, tree.id, PersonCreate.model_validate(body), actor
        )
        ids[p.key] = person.id

    for parents, children in FAMILIES:
        for child in children:
            for parent in parents:
                await rel_service.create_parent_child(
                    session,
                    tree.id,
                    ParentChildCreate(parent_id=ids[parent], child_id=ids[child]),
                    actor,
                )
    for a, b, start, place, end, reason in MARRIAGES:
        await rel_service.create_partnership(
            session,
            tree.id,
            PartnershipCreate.model_validate(
                {
                    "person_a_id": ids[a],
                    "person_b_id": ids[b],
                    "start_date": start,
                    "place_id": places.get(place or ""),
                    "end_date": end,
                    "end_reason": reason,
                }
            ),
            actor,
        )

    events: list[dict[str, Any]] = [
        {
            "type": "burial",
            "who": "stepan",
            "date": yr(1931, month=11, day=5),
            "place": "sorochyntsi",
            "cemetery_name": "Сільське кладовище Великих Сорочинців",
            "burial_plot": "Ряд 4, місце 12",
            "latitude": "50.024100",
            "longitude": "33.936800",
        },
        {
            "type": "military_service",
            "who": "petro",
            "title": "Служба в Червоній армії",
            "date": {"year": 1941, "end_year": 1944, "precision": "between"},
        },
        {
            "type": "education",
            "who": "oleksandr",
            "title": "Харківський інженерно-будівельний інститут",
            "date": {"year": 1936, "end_year": 1941, "precision": "between"},
            "place": "kharkiv",
        },
        {
            "type": "residence",
            "who": "halyna",
            "title": "Переїзд до Львова",
            "date": yr(1944),
            "place": "lviv",
        },
        {
            "type": "emigration",
            "who": "olha",
            "title": "Еміграція до Канади",
            "date": yr(1949, month=5),
            "place": "lviv",
            "description": "Виїхала через табори для переміщених осіб у Німеччині.",
        },
        {"type": "immigration", "who": "olha", "date": yr(1949, month=9), "place": "toronto"},
        {
            "type": "award",
            "who": "volodymyr",
            "title": "Заслужений будівельник України",
            "date": yr(1998),
        },
        {
            "type": "graduation",
            "who": "andrii",
            "title": "Київський політехнічний інститут",
            "date": yr(1997),
            "place": "kyiv",
        },
    ]
    for ev in events:
        body = {k: v for k, v in ev.items() if k not in ("who", "place")}
        body["participants"] = [{"person_id": ids[ev["who"]]}]
        if ev.get("place"):
            body["place_id"] = places[ev["place"]]
        await event_service.create_event(session, tree.id, EventCreate.model_validate(body), actor)
    return tree


async def run(args: argparse.Namespace) -> int:
    try:
        async with get_sessionmaker()() as session:
            query = select(User).where(User.is_superadmin.is_(True), User.is_active.is_(True))
            if args.owner:
                query = select(User).where(User.email == args.owner.lower())
            owner = (await session.scalars(query.order_by(User.created_at))).first()
            if owner is None:
                print(
                    "no owner found: create a superadmin first (SUPERADMIN_* env vars)",
                    file=sys.stderr,
                )
                return 1
            tree = await seed(session, owner)
            if tree is None:
                print(f"seed: tree {TREE_NAME!r} already exists, nothing to do")
            else:
                print(f"seed: created {TREE_NAME!r} ({len(PEOPLE)} people) owned by {owner.email}")
            return 0
    finally:
        await get_engine().dispose()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m app.seed",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--owner", help="email of the tree owner (default: first superadmin)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    configure_logging(get_settings().log_level)
    return asyncio.run(run(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
