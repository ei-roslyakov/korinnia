"""Demo family: `python -m app.seed` (or `make seed`).

Creates the tree "Родина Коваленків (демо)" — 25 fictional people across 5 generations
(1860s–1980s) with Cyrillic and Latin names, places with historical names, life events,
burial details, an emigration to Canada, a biography and an illustrated portrait for every
person. Uses the regular services, so everything is validated and recorded in the history
like a manual edit.

Every user gets their own copy (new accounts automatically, through a background job; see
DEMO_TREE_FOR_NEW_USERS). Running it again does nothing for owners who already have one.
"""

from __future__ import annotations

import argparse
import asyncio
import io
import sys
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.dates import PartialDate
from app.core.db import get_engine, get_sessionmaker
from app.core.logging import configure_logging
from app.models import Person, Tree, User
from app.schemas.events import EventCreate
from app.schemas.persons import PersonCreate
from app.schemas.places import PlaceCreate
from app.schemas.relationships import ParentChildCreate, PartnershipCreate
from app.services import trees as tree_service
from app.services.context import Actor
from app.services.demo_portraits import HEAD_CROP, render_portrait
from app.services.genealogy import events as event_service
from app.services.genealogy import media as media_service
from app.services.genealogy import persons as person_service
from app.services.genealogy import places as place_service
from app.services.genealogy import relationships as rel_service
from app.storage import Storage, get_storage

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

# Short biographies (fictional) so the demo person pages are not empty.
BIOGRAPHIES: dict[str, str] = {
    "stepan": (
        "Сільський коваль у Великих Сорочинцях. Його кузня стояла біля шляху на Миргород, "
        "і на ярмарок до неї з'їжджалися з усієї округи.\n\n"
        "## Родина\n\nРазом із Параскою виховав сина Івана та доньку Марію."
    ),
    "paraska": (
        "Господиня і знана в селі вишивальниця. Її рушники досі зберігаються в родині. "
        "Пережила чоловіка майже на десять років."
    ),
    "ivan": (
        "Хлібороб, згодом бригадир у колгоспі. Зник безвісти на фронті 1944 року; "
        "останнього листа родина отримала з-під Корсуня."
    ),
    "mariia": (
        "Після заміжжя переїхала до Полтави, де працювала швачкою. "
        "Подруга дитинства казала про неї: «Марія все шила так, ніби на свято»."
    ),
    "yosyp": (
        "Залізничник зі Станиславова. Пам'ятав місто ще під Австро-Угорщиною "
        "і любив розповідати онукам про перший трамвай."
    ),
    "oleksandr": (
        "Інженер-будівельник, випускник Харківського інституту. Після війни відбудовував "
        "Львів, а згодом зводив житлові квартали Києва."
    ),
    "olha": (
        "Молодша сестра Галини. 1949 року через табори для переміщених осіб емігрувала до "
        "Канади, де разом з Михайлом відкрила невелику пекарню в Торонто."
    ),
    "volodymyr": (
        "Будівельник, як і батько. Заслужений будівельник України (1998). "
        "Зберігав родинний архів і записав перші спогади матері на касети."
    ),
    "andrii": (
        "Інженер, випускник Київської політехніки. Саме він почав складати цей родовід "
        "і зібрав світлини від родичів в Україні та Канаді."
    ),
    "stephen": (
        "Народився в Торонто. Вивчив українську від бабусі Ольги й 1992 року вперше "
        "приїхав в Україну знайомитися з родиною."
    ),
    "hanna": (
        "Родом із Полтави. Познайомилася з Іваном на Сорочинському ярмарку 1916 року. "
        "Овдовівши у війну, сама виростила сина Олександра і дочекалася онуків."
    ),
    "fedir": (
        "Полтавський столяр. Його меблі — комод і скриня з різьбленими квітами — досі "
        "стоять у домі онуків."
    ),
    "kateryna": (
        "Учителька початкової школи в Станиславові. Навчила грамоти половину вулиці "
        "й берегла родинну Біблію з записами народжень."
    ),
    "petro": (
        "Молодший брат Олександра. Мріяв стати агрономом, але 1941 року пішов на фронт "
        "і не повернувся. Його фронтові листи родина зберігає досі."
    ),
    "mykhailo": (
        "Львів'янин, пройшов табори для переміщених осіб у Німеччині, де познайомився з Ольгою. "
        "У Торонто став пекарем, і його маківники знала вся українська громада."
    ),
    "mykola": (
        "Син Марії та Федора. Усе життя пропрацював на Полтавському тепловозоремонтному "
        "заводі; пам'ятав кожну історію свого діда-коваля."
    ),
    "liudmyla": (
        "Харків'янка, лікарка-педіатр. Познайомилася з Володимиром на будові в Києві, "
        "куди приїхала на практику."
    ),
    "tetiana": (
        "Донька Олександра й Галини. Філологиня, перекладала з польської та англійської; "
        "саме вона листувалася з канадськими родичами."
    ),
    "andrii_b": (
        "Чоловік Тетяни, фотограф. Багато світлин у цьому родоводі зроблено його камерою."
    ),
    "oksana": (
        "Дружина Андрія, архітекторка. Разом вони відреставрували дідівську хату "
        "у Великих Сорочинцях."
    ),
    "nataliia": (
        "Сестра Андрія, історикиня. Знайшла в архіві метричну книгу з записом "
        "про народження прадіда Івана."
    ),
    "iryna": (
        "Донька Тетяни та Андрія Бондарів, музикантка. Записала колискові, "
        "які співала прабабуся Галина."
    ),
    "oleh": (
        "Син Тетяни та Андрія Бондарів, програміст. Допомагає родині зберігати цифровий архів."
    ),
    "emily": (
        "Народилася в Торонто. Вивчає історію української еміграції до Канади "
        "й записала спогади бабусі Ольги."
    ),
}

# (parents..., children)
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


async def demo_tree_of(session: AsyncSession, owner: User) -> Tree | None:
    return await session.scalar(
        select(Tree).where(
            Tree.is_demo.is_(True), Tree.owner_id == owner.id, Tree.deleted_at.is_(None)
        )
    )


def _years(p: P) -> str:
    born = PartialDate(**p.born).to_text() if p.born else ""
    died = PartialDate(**p.died).to_text() if p.died else ""
    short = [x.replace("abt ", "~").split("-")[0] for x in (born, died)]
    return " – ".join(x for x in short if x) if died else short[0]


# Bump when the portrait drawing changes: `make seed` then redraws generated portraits that
# are still in use (a photo a user uploaded or chose instead is never touched).
PORTRAIT_VERSION = 2


def _portrait_file(p: P) -> str:
    return f"portrait-v{PORTRAIT_VERSION}-{p.key}.jpg"


def _is_generated_portrait(filename: str, p: P) -> bool:
    return filename in (
        f"portrait-{p.key}.jpg",
        *(f"portrait-v{v}-{p.key}.jpg" for v in range(2, 10)),
    )


def _portrait_age(p: P) -> int:
    """Age to draw: mid-life, or the person's current age if they are young."""
    born = (p.born or {}).get("year") or 1900
    end = (p.died or {}).get("year") or 2026
    return max(20, min(int((end - born) * 0.6), 55 if p.died else 48))


async def _store_portrait(
    session: AsyncSession,
    storage: Storage,
    tree: Tree,
    person: Person,
    index: int,
    p: P,
    actor: Actor,
) -> Any:
    """Draw, store (like an upload) and set as the person's portrait; returns the media id."""
    name = f"{p.first} {p.last}" if not p.latin_primary else " ".join(p.latin or ())
    data = render_portrait(
        name=name,
        years=_years(p),
        gender=p.gender,
        birth_year=(p.born or {}).get("year"),
        seed=index,
        age=_portrait_age(p),
    )
    media = await media_service.upload_media(
        session,
        storage,
        tree.id,
        media_service.Upload(file=io.BytesIO(data), filename=_portrait_file(p), size=len(data)),
        actor=actor,
        title="Портрет (ілюстрація)",
        person_id=person.id,
        allow_duplicate=True,
    )
    person.primary_photo_id = media.id
    person.primary_photo_crop = dict(HEAD_CROP)
    person.avatar_key = None  # redrawn by the worker
    await session.commit()
    return media.id


async def _portraits(
    session: AsyncSession, storage: Storage, tree: Tree, ids: dict[str, Any], actor: Actor
) -> list[tuple[Any, Any]]:
    """An illustrated portrait per person."""
    stored = []
    for i, p in enumerate(PEOPLE):
        person = await session.get(Person, ids[p.key])
        if person is not None:
            stored.append(
                (await _store_portrait(session, storage, tree, person, i, p, actor), person.id)
            )
    return stored


async def complete_demo(
    session: AsyncSession, tree: Tree, owner: User, *, storage: Storage | None = None
) -> int:
    """Bring an older demo copy up to date: missing biographies, missing portraits, and
    generated portraits from an older drawing version. Never touches what the user wrote or
    a photo they chose. Returns the number of people updated."""
    from app.jobs.queue import enqueue_avatar, enqueue_media_processing
    from app.models import MediaFile, PersonName

    actor = Actor(owner, ip="seed")
    store = storage or get_storage()
    by_name: dict[tuple[str | None, str | None], Person] = {}
    rows = await session.execute(
        select(PersonName.first_name, PersonName.last_name, Person)
        .join(Person, Person.id == PersonName.person_id)
        .where(Person.tree_id == tree.id, Person.deleted_at.is_(None))
    )
    for first, last, row in rows:
        by_name.setdefault((first, last), row)
    updated = 0
    for i, p in enumerate(PEOPLE):
        person = by_name.get((p.first, p.last))
        if person is None:
            continue
        changed = False
        if not person.biography and p.key in BIOGRAPHIES:
            person.biography = BIOGRAPHIES[p.key]
            await session.commit()
            changed = True
        current = (
            await session.get(MediaFile, person.primary_photo_id)
            if person.primary_photo_id
            else None
        )
        outdated = (
            current is not None
            and current.deleted_at is None
            and _is_generated_portrait(current.original_filename, p)
            and current.original_filename != _portrait_file(p)
        )
        if person.primary_photo_id is None or outdated:
            media_id = await _store_portrait(session, store, tree, person, i, p, actor)
            if outdated and current is not None:
                await media_service.delete_media(session, current, actor)  # to the trash
            await enqueue_media_processing(media_id)
            await enqueue_avatar(person.id)
            changed = True
        updated += changed
    return updated


async def seed(
    session: AsyncSession,
    owner: User,
    *,
    storage: Storage | None = None,
    portraits: bool = True,
) -> Tree | None:
    """Create `owner`'s copy of the demo family (None if they already have one)."""
    if await demo_tree_of(session, owner):
        return None
    actor = Actor(owner, ip="seed")
    tree = await tree_service.create_tree(
        session,
        name=TREE_NAME,
        description="Вигадана демонстраційна родина: п'ять поколінь, 1860-ті — 1980-ті.",
        owner=owner,
        actor=actor,
        is_demo=True,
    )
    places = {
        key: (await place_service.create_place(session, tree.id, PlaceCreate(**data), actor)).id
        for key, data in PLACES.items()
    }
    ids: dict[str, Any] = {}
    for p in PEOPLE:
        body: dict[str, Any] = {"gender": p.gender, "names": _names(p), **p.extra}
        body.setdefault("biography", BIOGRAPHIES.get(p.key))
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

    if portraits:
        from app.jobs.queue import enqueue_avatar, enqueue_media_processing

        for media_id, person_id in await _portraits(
            session, storage or get_storage(), tree, ids, actor
        ):
            await enqueue_media_processing(media_id)
            await enqueue_avatar(person_id)
    return tree


async def run(args: argparse.Namespace) -> int:
    from app.jobs.app import app as procrastinate_app

    try:
        # The job queue must be open: portraits are processed by the worker.
        async with procrastinate_app.open_async(), get_sessionmaker()() as session:
            if args.all_users:
                owners = list(
                    await session.scalars(
                        select(User).where(User.is_active.is_(True)).order_by(User.created_at)
                    )
                )
            else:
                query = select(User).where(User.is_superadmin.is_(True), User.is_active.is_(True))
                if args.owner:
                    query = select(User).where(User.email == args.owner.lower())
                first = (await session.scalars(query.order_by(User.created_at))).first()
                owners = [first] if first else []
            if not owners:
                print(
                    "no owner found: create a superadmin first (SUPERADMIN_* env vars)",
                    file=sys.stderr,
                )
                return 1
            for owner in owners:
                email = owner.email
                try:
                    tree = await seed(session, owner)
                except IntegrityError:  # created concurrently (e.g. by the worker)
                    await session.rollback()
                    await session.refresh(owner)
                    tree = None
                if tree is None:
                    existing = await demo_tree_of(session, owner)
                    filled = await complete_demo(session, existing, owner) if existing else 0
                    print(
                        f"seed: {email} already has {TREE_NAME!r}"
                        + (f"; added biographies / portraits for {filled} people" if filled else "")
                    )
                else:
                    print(f"seed: created {TREE_NAME!r} ({len(PEOPLE)} people) for {email}")
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
    parser.add_argument(
        "--all-users", action="store_true", help="give every active user their own copy"
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    configure_logging(get_settings().log_level)
    return asyncio.run(run(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
