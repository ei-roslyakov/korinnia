"""Demo family: `python -m app.seed` (or `make seed`).

Creates the tree "Родина Коваленків (демо)" — 66 fictional people across 7 generations
(1830s–2010s) with several root families, Cyrillic and Latin names, places with historical
names, life events, burial details, two emigrations to Canada, a biography and an
illustrated portrait for every person. Uses the regular services, so everything is validated
and recorded in the history like a manual edit.

Every user gets their own copy (new accounts automatically, through a background job; see
DEMO_TREE_FOR_NEW_USERS). Running it again brings existing copies up to date (people added
in a newer version of the demo, missing biographies and portraits) without touching what
their owners changed.
"""

from __future__ import annotations

import argparse
import asyncio
import functools
import io
import sys
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.dates import PartialDate
from app.core.db import get_engine, get_sessionmaker
from app.core.enums import DatePrecision
from app.core.errors import AppError
from app.core.logging import configure_logging
from app.models import Person, Tree, TreeRole, User
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
from app.services.genealogy.common import set_date
from app.storage import Storage, get_storage

TREE_NAME = "Родина Коваленків (демо)"
DESCRIPTION = (
    "Вигадана демонстраційна родина: сім поколінь, 1830-ті — 2010-ті, кілька родових гілок "
    "з Полтавщини, Прикарпаття, Слобожанщини й Канади."
)
# The first version's description; replaced in older copies unless the owner changed it.
OLD_DESCRIPTION = "Вигадана демонстраційна родина: п'ять поколінь, 1860-ті — 1980-ті."

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
    "myrhorod": {
        "name": "Миргород",
        "region": "Полтавська область",
        "country": "Україна",
        "latitude": "49.967600",
        "longitude": "33.608600",
        "historical_names": [{"name": "Миргород, Полтавська губернія", "until_year": 1923}],
    },
    "kolomyia": {
        "name": "Коломия",
        "region": "Івано-Франківська область",
        "country": "Україна",
        "latitude": "48.531000",
        "longitude": "25.036500",
        "historical_names": [
            {"name": "Kołomyja", "from_year": 1919, "until_year": 1939, "note": "У складі Польщі"},
            {"name": "Kolomea", "until_year": 1918, "note": "Австро-Угорщина"},
        ],
    },
    "dnipro": {
        "name": "Дніпро",
        "region": "Дніпропетровська область",
        "country": "Україна",
        "latitude": "48.464700",
        "longitude": "35.046200",
        "historical_names": [
            {"name": "Катеринослав", "until_year": 1926},
            {"name": "Дніпропетровськ", "from_year": 1926, "until_year": 2016},
        ],
    },
    "winnipeg": {
        "name": "Winnipeg",
        "region": "Manitoba",
        "country": "Canada",
        "latitude": "49.895100",
        "longitude": "-97.138400",
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
    # --- Added in the second version of the demo (2026-10): two older generations, the
    # families of everyone who married in (several roots), side branches and the youngest
    # generation. Kept after the original 25 so their portraits stay the same.
    # Generation 0 (1830s)
    P(
        "hnat",
        "male",
        "Гнат",
        "Коваленко",
        born=yr(1834),
        born_in="sorochyntsi",
        died=yr(1899),
        died_in="sorochyntsi",
        latin=("Hnat", "Kovalenko"),
        extra={"occupation": "Коваль"},
    ),
    P(
        "yavdokha",
        "female",
        "Явдоха",
        "Коваленко",
        maiden="Дяченко",
        born=yr(1838, precision="approx"),
        born_in="sorochyntsi",
        died=yr(1905),
        died_in="sorochyntsi",
    ),
    P(
        "mykyta",
        "male",
        "Микита",
        "Бойко",
        born=yr(1838),
        born_in="sorochyntsi",
        died=yr(1902),
        died_in="sorochyntsi",
        extra={"occupation": "Чумак"},
    ),
    P(
        "horpyna",
        "female",
        "Горпина",
        "Бойко",
        born=yr(1842, precision="approx"),
        born_in="myrhorod",
        died=yr(1910),
        died_in="sorochyntsi",
    ),
    # Generation 1
    P(
        "omelian",
        "male",
        "Омелян",
        "Коваленко",
        "Гнатович",
        born=yr(1859),
        born_in="sorochyntsi",
        died=yr(1920),
        died_in="sorochyntsi",
    ),
    P(
        "uliana",
        "female",
        "Уляна",
        "Коваленко",
        maiden="Педенко",
        born=yr(1863),
        born_in="sorochyntsi",
        died=yr(1930),
        died_in="sorochyntsi",
    ),
    P(
        "vasyl_b",
        "male",
        "Василь",
        "Бойко",
        "Микитович",
        born=yr(1870),
        born_in="sorochyntsi",
        died=yr(1938),
        died_in="myrhorod",
    ),
    P(
        "trokhym",
        "male",
        "Трохим",
        "Мельник",
        born=yr(1860),
        born_in="poltava",
        died=yr(1921),
        died_in="poltava",
        extra={"occupation": "Мірошник"},
    ),
    P(
        "olena_m",
        "female",
        "Олена",
        "Мельник",
        maiden="Савченко",
        born=yr(1864),
        born_in="poltava",
        died=yr(1933),
        died_in="poltava",
    ),
    P(
        "ostap",
        "male",
        "Остап",
        "Ткач",
        born=yr(1855),
        born_in="poltava",
        died=yr(1920),
        died_in="poltava",
        extra={"occupation": "Столяр"},
    ),
    P(
        "marfa",
        "female",
        "Марфа",
        "Ткач",
        born=yr(1860, precision="approx"),
        born_in="poltava",
        died=yr(1928),
        died_in="poltava",
    ),
    P(
        "mykhailo_sh",
        "male",
        "Михайло",
        "Шевчук",
        born=yr(1855),
        born_in="kolomyia",
        died=yr(1915),
        died_in="ivano",
        latin=("Michał", "Szewczuk"),
        extra={"occupation": "Кравець", "religion": "Греко-католик"},
    ),
    P(
        "kseniia",
        "female",
        "Ксенія",
        "Шевчук",
        born=yr(1859),
        born_in="kolomyia",
        died=yr(1931),
        died_in="ivano",
    ),
    P(
        "petro_h",
        "male",
        "Петро",
        "Гнатюк",
        born=yr(1860),
        born_in="kolomyia",
        died=yr(1930),
        died_in="kolomyia",
        extra={"occupation": "Дяк"},
    ),
    P(
        "mariia_h",
        "female",
        "Марія",
        "Гнатюк",
        born=yr(1864),
        born_in="kolomyia",
        died=yr(1940),
        died_in="kolomyia",
    ),
    # Generation 2
    P(
        "sava",
        "male",
        "Сава",
        "Коваленко",
        "Омелянович",
        born=yr(1888),
        born_in="sorochyntsi",
        died=yr(1933),
        died_in="sorochyntsi",
        extra={"short_summary": "Загинув під час Голодомору."},
    ),
    P(
        "hryhorii",
        "male",
        "Григорій",
        "Мельник",
        "Трохимович",
        born=yr(1897),
        born_in="poltava",
        died=yr(1964),
        died_in="dnipro",
    ),
    P(
        "anna_sh",
        "female",
        "Анна",
        "Гуменюк",
        "Михайлівна",
        maiden="Шевчук",
        born=yr(1890),
        born_in="ivano",
        died=yr(1979),
        died_in="winnipeg",
        latin=("Anna", "Humeniuk"),
    ),
    P(
        "ivan_h",
        "male",
        "Іван",
        "Гуменюк",
        born=yr(1886),
        born_in="kolomyia",
        died=yr(1951),
        died_in="winnipeg",
        latin=("John", "Humeniuk"),
        extra={"occupation": "Фермер"},
    ),
    # Generation 3
    P(
        "peter_h",
        "male",
        "Петро",
        "Гуменюк",
        "Іванович",
        born=yr(1915),
        born_in="winnipeg",
        died=yr(1990),
        died_in="winnipeg",
        latin=("Peter", "Humeniuk"),
        latin_primary=True,
    ),
    P(
        "nina",
        "female",
        "Ніна",
        "Мельник",
        "Григорівна",
        born=yr(1925),
        born_in="dnipro",
        died=yr(2003),
        died_in="dnipro",
        extra={"occupation": "Бібліотекарка"},
    ),
    P(
        "viktor",
        "male",
        "Віктор",
        "Романенко",
        born=yr(1925),
        born_in="kharkiv",
        died=yr(1999),
        died_in="kharkiv",
    ),
    P(
        "zoia",
        "female",
        "Зоя",
        "Романенко",
        born=yr(1928),
        born_in="kharkiv",
        died=yr(2011),
        died_in="kharkiv",
    ),
    P(
        "vira",
        "female",
        "Віра",
        "Ткач",
        maiden="Головко",
        born=yr(1920),
        born_in="poltava",
        died=yr(1990),
        died_in="poltava",
    ),
    # Generation 4
    P(
        "mary_h",
        "female",
        "Mary",
        "Humeniuk",
        born=yr(1945),
        born_in="winnipeg",
        latin=("Mary", "Humeniuk"),
        latin_primary=True,
    ),
    P(
        "yurii",
        "male",
        "Юрій",
        "Ткач",
        "Миколайович",
        born=yr(1946),
        born_in="poltava",
        died=yr(2019),
        died_in="poltava",
        extra={"occupation": "Інженер-залізничник"},
    ),
    P(
        "larysa",
        "female",
        "Лариса",
        "Ткач",
        maiden="Мороз",
        born=yr(1948),
        born_in="poltava",
        extra={"occupation": "Економістка"},
    ),
    P("serhii", "male", "Сергій", "Литвин", born=yr(1950), born_in="dnipro"),
    P("valentyna", "female", "Валентина", "Литвин", born=yr(1952), born_in="dnipro"),
    P(
        "sarah",
        "female",
        "Sarah",
        "Tkachuk",
        maiden="Miller",
        born=yr(1954),
        born_in="toronto",
        latin=("Sarah", "Tkachuk"),
        latin_primary=True,
    ),
    # Generation 5
    P("olena_t", "female", "Олена", "Ткач", "Юріївна", born=yr(1972), born_in="poltava"),
    P("ihor", "male", "Ігор", "Савчук", born=yr(1970), born_in="poltava"),
    P("maksym", "male", "Максим", "Гончаренко", born=yr(1977), born_in="kharkiv"),
    P("yuliia", "female", "Юлія", "Бондар", maiden="Кравець", born=yr(1984), born_in="kyiv"),
    P(
        "daniel",
        "male",
        "Daniel",
        "Harris",
        born=yr(1978),
        born_in="toronto",
        latin=("Daniel", "Harris"),
        latin_primary=True,
    ),
    # Generation 6 (2000s–2010s)
    P("bohdan", "male", "Богдан", "Ткач", born=yr(2001), born_in="poltava"),
    P(
        "taras",
        "male",
        "Тарас",
        "Коваленко",
        "Андрійович",
        born=yr(2005, month=4, day=18),
        born_in="kyiv",
        latin=("Taras", "Kovalenko"),
    ),
    P("daryna", "female", "Дарина", "Гончаренко", "Максимівна", born=yr(2008), born_in="kyiv"),
    P("sofiia", "female", "Софія", "Коваленко", "Андріївна", born=yr(2009), born_in="kyiv"),
    P(
        "olivia",
        "female",
        "Olivia",
        "Harris",
        born=yr(2011),
        born_in="toronto",
        latin=("Olivia", "Harris"),
        latin_primary=True,
    ),
    P("danylo", "male", "Данило", "Бондар", "Олегович", born=yr(2014), born_in="kyiv"),
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
    "hnat": (
        "Найдавніший відомий предок Коваленків. Від нього пішло ковальство в родині: "
        "кузню біля миргородського шляху він передав синові Степанові."
    ),
    "yavdokha": (
        "Дружина Гната, родом із Дяченків. Народила сімох дітей, із яких вижили двоє — "
        "Омелян і Степан."
    ),
    "mykyta": (
        "Чумак із Великих Сорочинців. Возив сіль із Криму, а з останньої мандрівки привіз "
        "дружині мідний хрестик, що досі передається в родині."
    ),
    "horpyna": ("Родом із Миргорода. Знала цілющі трави, і до неї по пораду ходило все село."),
    "omelian": (
        "Старший брат Степана. Хліборобствував на батьковій землі й мав найкращий у селі "
        "сад, де росли груші, щеплені ще дідом."
    ),
    "uliana": "Дружина Омеляна, ткаля. Її килими з півнями прикрашали хати всієї родини.",
    "vasyl_b": (
        "Молодший брат Параски. Учителював у Миргороді, листувався зі Степаном "
        "і хрестив його дітей."
    ),
    "trokhym": (
        "Мірошник із Полтави. Його млин на Ворсклі мололи і для Мельників, і для сусідніх "
        "сіл; звідси й прізвище роду."
    ),
    "olena_m": (
        "Дружина Трохима, з роду Савченків. Вела господарство млина й виховала "
        "доньку Ганну та сина Григорія."
    ),
    "ostap": (
        "Полтавський столяр, батько Федора. Навчив сина ремесла, тож столярство "
        "в родині Ткачів тримається вже кілька поколінь."
    ),
    "marfa": "Дружина Остапа. Співала в церковному хорі й пекла найкращі в околиці паляниці.",
    "mykhailo_sh": (
        "Кравець із Коломиї, згодом переїхав до Станиславова. Шив святкові сурдути "
        "й навчив дітей поважати добру роботу."
    ),
    "kseniia": (
        "Дружина Михайла. Пережила його на шістнадцять років і дочекалася онучок Галини та Ольги."
    ),
    "petro_h": (
        "Дяк у Коломиї. Гарно писав, тож саме його рукою зроблено частину записів "
        "у родинній Біблії."
    ),
    "mariia_h": (
        "Дружина Петра Гнатюка. Виховала доньку Катерину, яка стала вчителькою, "
        "і пишалася, що в родині є «вчена людина»."
    ),
    "sava": (
        "Син Омеляна. Загинув 1933 року під час Голодомору; його ім'я родина "
        "згадує щороку в листопаді."
    ),
    "hryhorii": (
        "Брат Ганни. Пройшов Першу світову війну, після неї оселився в Катеринославі "
        "й працював на металургійному заводі."
    ),
    "anna_sh": (
        "Сестра Йосипа. 1910 року разом із чоловіком емігрувала до Канади; у Вінніпезі "
        "вони мали ферму й допомагали новоприбулим українцям."
    ),
    "ivan_h": (
        "Чоловік Анни, з Коломиї. У Канаді спочатку будував залізницю, потім "
        "обробляв власну землю в Манітобі."
    ),
    "peter_h": (
        "Народився у Вінніпезі. Учитель і хормейстер українського хору; "
        "завдяки його листам канадські родини знайшли одна одну."
    ),
    "nina": (
        "Донька Григорія. Бібліотекарка в Дніпрі, берегла фотографії Мельників "
        "і передала їх Наталії."
    ),
    "viktor": "Батько Людмили, харківський лікар-терапевт. Від нього Людмила взяла професію.",
    "zoia": "Мати Людмили, вчителька музики. Учила грати на фортепіано і онуків.",
    "vira": "Дружина Миколи, медсестра. Разом вони виростили сина Юрія.",
    "mary_h": (
        "Донька Петра Гуменюка. Бібліотекарка у Вінніпезі, зібрала архів листів "
        "канадської гілки родини."
    ),
    "yurii": (
        "Син Миколи, інженер-залізничник. Сорок років працював на Південній залізниці "
        "і, як батько, любив розповідати родинні історії."
    ),
    "larysa": (
        "Перша дружина Юрія, мати Олени. Шлюб розпався 1978 року, але вона й далі "
        "приїжджала на родинні свята."
    ),
    "ihor": "Батько Богдана, музикант. Разом з Оленою вони живуть у Полтаві без шлюбу.",
    "serhii": "Батько Оксани, інженер із Дніпра.",
    "valentyna": "Мати Оксани, учителька математики.",
    "sarah": (
        "Дружина Степана (Stephen), канадка. Вивчила українську, щоб розмовляти "
        "зі свекрухою Ольгою."
    ),
    "olena_t": "Донька Юрія, учителька історії в Полтаві.",
    "maksym": "Чоловік Наталії, журналіст.",
    "yuliia": "Дружина Олега, дизайнерка.",
    "daniel": "Чоловік Emily, учитель історії з Торонто.",
    "bohdan": "Син Олени, студент-інженер — четверте покоління Ткачів, що працює руками.",
    "taras": "Син Андрія та Оксани. Вивчає історію й допомагає батькові з родоводом.",
    "daryna": "Донька Наталії та Максима. Малює родинне дерево для шкільного проєкту.",
    "sofiia": "Донька Андрія та Оксани, наймолодша Коваленко.",
    "olivia": "Донька Emily та Daniel. Вчить українську в суботній школі в Торонто.",
    "danylo": "Син Олега та Юлії, наймолодший у родоводі.",
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
    (("stephen", "sarah"), ["emily"]),
    # Second version: the older generations and the families of those who married in.
    (("hnat", "yavdokha"), ["omelian", "stepan"]),
    (("mykyta", "horpyna"), ["paraska", "vasyl_b"]),
    (("omelian", "uliana"), ["sava"]),
    (("trokhym", "olena_m"), ["hanna", "hryhorii"]),
    (("ostap", "marfa"), ["fedir"]),
    (("mykhailo_sh", "kseniia"), ["yosyp", "anna_sh"]),
    (("petro_h", "mariia_h"), ["kateryna"]),
    (("hryhorii",), ["nina"]),
    (("anna_sh", "ivan_h"), ["peter_h"]),
    (("peter_h",), ["mary_h"]),
    (("viktor", "zoia"), ["liudmyla"]),
    (("mykola", "vira"), ["yurii"]),
    (("yurii", "larysa"), ["olena_t"]),
    (("olena_t", "ihor"), ["bohdan"]),
    (("serhii", "valentyna"), ["oksana"]),
    (("andrii", "oksana"), ["taras", "sofiia"]),
    (("nataliia", "maksym"), ["daryna"]),
    (("oleh", "yuliia"), ["danylo"]),
    (("emily", "daniel"), ["olivia"]),
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
    ("hnat", "yavdokha", yr(1857, precision="approx"), "sorochyntsi", yr(1899), "death"),
    ("mykyta", "horpyna", yr(1864), "myrhorod", None, None),
    ("omelian", "uliana", yr(1885), "sorochyntsi", None, None),
    ("trokhym", "olena_m", yr(1888), "poltava", None, None),
    ("ostap", "marfa", yr(1882), "poltava", None, None),
    ("mykhailo_sh", "kseniia", yr(1880), "kolomyia", None, None),
    ("petro_h", "mariia_h", yr(1885), "kolomyia", None, None),
    ("anna_sh", "ivan_h", yr(1909), "kolomyia", None, None),
    ("viktor", "zoia", yr(1949), "kharkiv", None, None),
    ("mykola", "vira", yr(1945), "poltava", None, None),
    ("yurii", "larysa", yr(1970), "poltava", yr(1978), "divorce"),
    ("olena_t", "ihor", yr(2000), None, None, None),
    ("serhii", "valentyna", yr(1975), "dnipro", None, None),
    ("stephen", "sarah", yr(1978, month=6, day=10), "toronto", None, None),
    ("nataliia", "maksym", yr(2006), "kyiv", None, None),
    ("oleh", "yuliia", yr(2011), "kyiv", None, None),
    ("emily", "daniel", yr(2009), "toronto", None, None),
]

# Couples that are not married (everyone else in MARRIAGES is).
UNMARRIED: set[tuple[str, str]] = {("olena_t", "ihor")}

# Life events besides birth and death; "who" are the principals.
EVENTS: list[dict[str, Any]] = [
    {
        "type": "burial",
        "who": ["stepan"],
        "date": yr(1931, month=11, day=5),
        "place": "sorochyntsi",
        "cemetery_name": "Сільське кладовище Великих Сорочинців",
        "burial_plot": "Ряд 4, місце 12",
        "latitude": "50.024100",
        "longitude": "33.936800",
    },
    {
        "type": "military_service",
        "who": ["petro"],
        "title": "Служба в Червоній армії",
        "date": {"year": 1941, "end_year": 1944, "precision": "between"},
    },
    {
        "type": "education",
        "who": ["oleksandr"],
        "title": "Харківський інженерно-будівельний інститут",
        "date": {"year": 1936, "end_year": 1941, "precision": "between"},
        "place": "kharkiv",
    },
    {
        "type": "residence",
        "who": ["halyna"],
        "title": "Переїзд до Львова",
        "date": yr(1944),
        "place": "lviv",
    },
    {
        "type": "emigration",
        "who": ["olha"],
        "title": "Еміграція до Канади",
        "date": yr(1949, month=5),
        "place": "lviv",
        "description": "Виїхала через табори для переміщених осіб у Німеччині.",
    },
    {"type": "immigration", "who": ["olha"], "date": yr(1949, month=9), "place": "toronto"},
    {
        "type": "award",
        "who": ["volodymyr"],
        "title": "Заслужений будівельник України",
        "date": yr(1998),
    },
    {
        "type": "graduation",
        "who": ["andrii"],
        "title": "Київський політехнічний інститут",
        "date": yr(1997),
        "place": "kyiv",
    },
    # Second version
    {
        "type": "burial",
        "who": ["hnat"],
        "date": yr(1899),
        "place": "sorochyntsi",
        "cemetery_name": "Сільське кладовище Великих Сорочинців",
    },
    {
        "type": "emigration",
        "who": ["anna_sh", "ivan_h"],
        "title": "Еміграція до Канади",
        "date": yr(1910, month=4),
        "place": "kolomyia",
        "description": "Пароплавом із Гамбурга до Галіфакса, далі потягом до Вінніпега.",
    },
    {
        "type": "immigration",
        "who": ["anna_sh", "ivan_h"],
        "date": yr(1910, month=5),
        "place": "winnipeg",
    },
    {
        "type": "military_service",
        "who": ["hryhorii"],
        "title": "Служба в армії під час Першої світової війни",
        "date": {"year": 1915, "end_year": 1918, "precision": "between"},
    },
    {
        "type": "residence",
        "who": ["hryhorii"],
        "title": "Переїзд до Катеринослава",
        "date": yr(1922),
        "place": "dnipro",
    },
    {
        "type": "education",
        "who": ["yurii"],
        "title": "Харківський інститут інженерів залізничного транспорту",
        "date": {"year": 1964, "end_year": 1969, "precision": "between"},
        "place": "kharkiv",
    },
    {
        "type": "occupation",
        "who": ["peter_h"],
        "title": "Хормейстер українського хору",
        "date": {"year": 1946, "end_year": 1985, "precision": "between"},
        "place": "winnipeg",
    },
    {
        "type": "graduation",
        "who": ["taras"],
        "title": "Ліцей",
        "date": yr(2022, month=6),
        "place": "kyiv",
    },
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
                "script": native["script"],
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


# Portraits are the same in every copy: draw each once per process (a demo sign-in then
# takes well under a second instead of three).
_render_portrait = functools.lru_cache(maxsize=256)(render_portrait)


def _portrait_bytes(index: int, p: P) -> bytes:
    name = f"{p.first} {p.last}" if not p.latin_primary else " ".join(p.latin or ())
    return _render_portrait(
        name=name,
        years=_years(p),
        gender=p.gender,
        birth_year=(p.born or {}).get("year"),
        seed=index,
        age=_portrait_age(p),
    )


def warm_portraits() -> None:
    """Draw every portrait into the cache (at start-up when the public demo is on)."""
    for i, p in enumerate(PEOPLE):
        _portrait_bytes(i, p)


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


PORTRAIT_TITLE_OLD = "Портрет (ілюстрація)"  # before the album: one title for every portrait
PORTRAIT_NOTE = "Ілюстрований портрет, намальований для демонстраційного родоводу."


def _portrait_meta(p: P, places: dict[str, Any]) -> dict[str, Any]:
    """Title, description, date and place of a generated portrait, so the family album shows
    who it is, when and where: the name, the first paragraph of the biography, the year the
    drawing shows the person at (approximate) and their home place."""
    name = f"{p.first} {p.last}" if not p.latin_primary else " ".join(p.latin or ())
    bio = BIOGRAPHIES.get(p.key, "").split("\n\n", 1)[0].strip()
    born = (p.born or {}).get("year")
    year = min(born + _portrait_age(p), 2025) if born else None
    return {
        "title": name,
        "description": f"{bio}\n\n{PORTRAIT_NOTE}" if bio else PORTRAIT_NOTE,
        "date": PartialDate(year=year, precision=DatePrecision.approx) if year else None,
        "place_id": places.get(p.born_in or p.died_in or ""),
    }


def _describe_portrait(media: Any, p: P, places: dict[str, Any]) -> None:
    meta = _portrait_meta(p, places)
    media.title = meta["title"]
    media.description = meta["description"]
    if meta["date"]:
        set_date(media, "date", "date_sort", meta["date"])
    media.place_id = meta["place_id"]


async def _store_portrait(
    session: AsyncSession,
    storage: Storage,
    tree: Tree,
    person: Person,
    index: int,
    p: P,
    actor: Actor,
    places: dict[str, Any],
) -> Any:
    """Draw, store (like an upload) and set as the person's portrait; returns the media id."""
    data = _portrait_bytes(index, p)
    media = await media_service.upload_media(
        session,
        storage,
        tree.id,
        media_service.Upload(file=io.BytesIO(data), filename=_portrait_file(p), size=len(data)),
        actor=actor,
        person_id=person.id,
        allow_duplicate=True,
    )
    _describe_portrait(media, p, places)
    person.primary_photo_id = media.id
    person.primary_photo_crop = dict(HEAD_CROP)
    person.avatar_key = None  # redrawn by the worker
    await session.commit()
    return media.id


async def _portraits(
    session: AsyncSession,
    storage: Storage,
    tree: Tree,
    ids: dict[str, Any],
    actor: Actor,
    only: set[str] | None = None,
) -> list[tuple[Any, Any]]:
    """An illustrated portrait per person (or per person in `only`)."""
    stored = []
    places = await _places(session, tree, actor)
    for i, p in enumerate(PEOPLE):
        if only is not None and p.key not in only:
            continue
        person = await session.get(Person, ids[p.key]) if p.key in ids else None
        if person is not None:
            stored.append(
                (
                    await _store_portrait(session, storage, tree, person, i, p, actor, places),
                    person.id,
                )
            )
    return stored


def _person_body(p: P, places: dict[str, Any]) -> PersonCreate:
    body: dict[str, Any] = {"gender": p.gender, "names": _names(p), **p.extra}
    body.setdefault("biography", BIOGRAPHIES.get(p.key))
    if p.born:
        body["birth"] = {"date": p.born, "place_id": places.get(p.born_in or "")}
    if p.died:
        body["death"] = {"date": p.died, "place_id": places.get(p.died_in or "")}
    return PersonCreate.model_validate(body)


def _wanted(keys: Iterable[str], ids: dict[str, Any], only: set[str] | None) -> bool:
    """All `keys` exist, and (when extending) at least one of them is new."""
    keys = list(keys)
    return all(k in ids for k in keys) and (only is None or any(k in only for k in keys))


async def _relations(
    session: AsyncSession,
    tree_id: Any,
    ids: dict[str, Any],
    places: dict[str, Any],
    actor: Actor,
    only: set[str] | None = None,
) -> None:
    """Parent links, marriages and life events between people in `ids`. With `only`, just
    those that involve a newly added person (an existing copy keeps what it has)."""
    for parents, children in FAMILIES:
        for child in children:
            for parent in parents:
                if not _wanted((parent, child), ids, only):
                    continue
                try:
                    await rel_service.create_parent_child(
                        session,
                        tree_id,
                        ParentChildCreate(parent_id=ids[parent], child_id=ids[child]),
                        actor,
                    )
                except AppError:  # already linked, or the owner changed this part
                    await session.rollback()
    for a, b, start, place, end, reason in MARRIAGES:
        if not _wanted((a, b), ids, only):
            continue
        try:
            await rel_service.create_partnership(
                session,
                tree_id,
                PartnershipCreate.model_validate(
                    {
                        "person_a_id": ids[a],
                        "person_b_id": ids[b],
                        "type": "partnership" if (a, b) in UNMARRIED else "marriage",
                        "start_date": start,
                        "place_id": places.get(place or ""),
                        "end_date": end,
                        "end_reason": reason,
                    }
                ),
                actor,
            )
        except AppError:
            await session.rollback()
    for ev in EVENTS:
        if not _wanted(ev["who"], ids, only):
            continue
        body = {k: v for k, v in ev.items() if k not in ("who", "place")}
        body["participants"] = [{"person_id": ids[k]} for k in ev["who"]]
        if ev.get("place"):
            body["place_id"] = places[ev["place"]]
        await event_service.create_event(session, tree_id, EventCreate.model_validate(body), actor)


# Family recipes and a tradition (D117), told in the family's voice like the biographies.
STORIES: list[dict[str, Any]] = [
    {
        "title": "Борщ баби Параски",
        "kind": "recipe",
        "occasion": "Неділя й храмове свято",
        "narrator": "за розповіддю онуки Марії",
        "people": ["paraska", "stepan"],
        "body": (
            "Параска варила борщ у печі, у великому глиняному горщику, і нікому не дозволяла "
            "зазирати під кришку, доки не «відпочине». Буряк брала лише свій, з городу за "
            "кузнею, а квасолю вимочувала звечора.\n\n"
            "Марія казала, що справжній смак давала заправка — товчене сало з часником, яке "
            "кидали в самому кінці."
        ),
        "recipe": {
            "servings": 8,
            "prep_minutes": 40,
            "cook_minutes": 150,
            "ingredients": [
                {"amount": "1 кг", "item": "свинячі реберця"},
                {"amount": "3 шт.", "item": "буряки"},
                {"amount": "½ голівки", "item": "капуста"},
                {"amount": "4 шт.", "item": "картоплини"},
                {"amount": "1 склянка", "item": "квасоля, вимочена звечора"},
                {"amount": "2 ст. л.", "item": "томатна паста"},
                {"amount": "50 г", "item": "сало, товчене з часником"},
            ],
            "steps": [
                "Зварити бульйон з реберець на повільному вогні (1,5 години).",
                "Додати квасолю й нарізану картоплю, варити 20 хвилин.",
                "Буряк натерти й потушкувати з томатом і ложкою оцту, додати до борщу.",
                "Покласти нашатковану капусту, варити ще 10 хвилин.",
                "Наприкінці заправити салом з часником, дати настоятися під кришкою.",
            ],
        },
    },
    {
        "title": "Вареники з вишнями від Валентини",
        "kind": "recipe",
        "occasion": "Літо, коли достигають вишні",
        "narrator": "Валентина Литвин",
        "people": ["valentyna", "oksana"],
        "body": (
            "Щочервня вся родина збиралася в Дніпрі ліпити вареники. Валентина вчила онуків "
            "защипувати краї «косичкою», а найкраще защипаний вареник діставався майстрові."
        ),
        "recipe": {
            "servings": 6,
            "prep_minutes": 60,
            "cook_minutes": 15,
            "ingredients": [
                {"amount": "500 г", "item": "борошно"},
                {"amount": "250 мл", "item": "кефір"},
                {"amount": "1 шт.", "item": "яйце"},
                {"amount": "600 г", "item": "вишні без кісточок"},
                {"amount": "3 ст. л.", "item": "цукор"},
            ],
            "steps": [
                "Замісити тісто з борошна, кефіру, яйця й дрібки солі; дати відпочити 30 хвилин.",
                "Вишні пересипати цукром, сік злити — він піде до підливи.",
                "Розкачати тісто, вирізати кружальця склянкою, викласти по 3–4 вишні.",
                "Защипнути краї й варити в підсоленій воді 3–4 хвилини після спливання.",
                "Подавати зі сметаною та вишневим соком.",
            ],
        },
    },
    {
        "title": "Свят-вечір: дванадцять страв і дідух",
        "kind": "tradition",
        "occasion": "Святий вечір",
        "narrator": "за спогадами родини",
        "people": ["stepan", "paraska"],
        "body": (
            "На Святий вечір Степан заносив до хати дідуха — сніп жита з останнього обжинку — "
            "і ставив у покуті. Параска стелила під скатертину сіно, а на стіл ставила "
            "дванадцять пісних страв, і першою — кутю.\n\n"
            "Вечеряти починали, щойно на небі з'являлася перша зірка. Одне місце за столом "
            "лишали порожнім — для тих, кого вже немає з родиною."
        ),
    },
]


async def _stories(session: AsyncSession, tree: Tree, ids: dict[str, Any], actor: Actor) -> int:
    """Add the demo's recipes and tradition that the copy does not have yet (one the owner
    deleted is not brought back: titles in the trash count)."""
    from app.models import Story
    from app.schemas.stories import StoryCreate
    from app.services.genealogy import stories as story_service

    have = set(await session.scalars(select(Story.title).where(Story.tree_id == tree.id)))
    added = 0
    for s in STORIES:
        if s["title"] in have:
            continue
        body = StoryCreate.model_validate(
            {k: v for k, v in s.items() if k != "people"}
            | {
                "status": "published",
                "person_ids": [ids[k] for k in s["people"] if k in ids],
            }
        )
        await story_service.create_story(session, tree.id, body, actor, TreeRole.admin)
        added += 1
    return added


async def _places(session: AsyncSession, tree: Tree, actor: Actor) -> dict[str, Any]:
    """Ids of the demo places in `tree`, creating those that are missing."""
    from app.models import Place

    rows = await session.execute(
        select(Place.name, Place.id).where(Place.tree_id == tree.id, Place.deleted_at.is_(None))
    )
    existing: dict[str, Any] = dict(rows.all())
    out = {}
    for key, data in PLACES.items():
        out[key] = (
            existing.get(data["name"])
            or (await place_service.create_place(session, tree.id, PlaceCreate(**data), actor)).id
        )
    return out


async def _extend(
    session: AsyncSession, tree: Tree, owner: User, actor: Actor, storage: Storage
) -> int:
    """Add the people (and their links and events) that an older copy of the demo does not
    have yet. Someone the owner deleted is not brought back: names in the trash count."""
    from app.models import PersonName

    rows = await session.execute(
        select(PersonName.first_name, PersonName.last_name, Person.id, Person.deleted_at)
        .join(Person, Person.id == PersonName.person_id)
        .where(Person.tree_id == tree.id)
    )
    seen: set[tuple[str | None, str | None]] = set()
    live: dict[tuple[str | None, str | None], Any] = {}
    for first, last, pid, deleted_at in rows:
        seen.add((first, last))
        if deleted_at is None:
            live.setdefault((first, last), pid)
    ids = {p.key: live[(p.first, p.last)] for p in PEOPLE if (p.first, p.last) in live}
    missing = [p for p in PEOPLE if (p.first, p.last) not in seen]
    if not missing:
        return 0
    places = await _places(session, tree, actor)
    for p in missing:
        ids[p.key] = (
            await person_service.create_person(session, tree.id, _person_body(p, places), actor)
        ).id
    new = {p.key for p in missing}
    await _relations(session, tree.id, ids, places, actor, only=new)
    if tree.description == OLD_DESCRIPTION:
        tree.description = DESCRIPTION
        await session.commit()
    from app.jobs.queue import enqueue_avatar, enqueue_media_processing

    for media_id, person_id in await _portraits(session, storage, tree, ids, actor, only=new):
        await enqueue_media_processing(media_id)
        await enqueue_avatar(person_id)
    return len(missing)


@dataclass
class DemoUpdate:
    added: int = 0  # people new in this version of the demo
    updated: int = 0  # biographies / portraits filled in or redrawn


async def complete_demo(
    session: AsyncSession, tree: Tree, owner: User, *, storage: Storage | None = None
) -> DemoUpdate:
    """Bring an older demo copy up to date: people added in newer versions of the demo,
    missing biographies, missing portraits, and generated portraits from an older drawing
    version. Never touches what the user wrote, a photo they chose or a person they
    deleted."""
    from app.jobs.queue import enqueue_avatar, enqueue_media_processing
    from app.models import MediaFile, PersonName

    actor = Actor(owner, ip="seed")
    store = storage or get_storage()
    result = DemoUpdate(added=await _extend(session, tree, owner, actor, store))
    places = await _places(session, tree, actor)
    by_name: dict[tuple[str | None, str | None], Person] = {}
    rows = await session.execute(
        select(PersonName.first_name, PersonName.last_name, Person)
        .join(Person, Person.id == PersonName.person_id)
        .where(Person.tree_id == tree.id, Person.deleted_at.is_(None))
    )
    for first, last, row in rows:
        by_name.setdefault((first, last), row)
    ids = {p.key: by_name[(p.first, p.last)].id for p in PEOPLE if (p.first, p.last) in by_name}
    result.updated += await _stories(session, tree, ids, actor)
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
        if (
            current is not None
            and current.original_filename == _portrait_file(p)
            and current.title == PORTRAIT_TITLE_OLD
            and current.description is None
        ):
            _describe_portrait(current, p, places)  # for the family album
            await session.commit()
            changed = True
        if person.primary_photo_id is None or outdated:
            media_id = await _store_portrait(session, store, tree, person, i, p, actor, places)
            if outdated and current is not None:
                await media_service.delete_media(session, current, actor)  # to the trash
            await enqueue_media_processing(media_id)
            await enqueue_avatar(person.id)
            changed = True
        result.updated += changed
    return result


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
        description=DESCRIPTION,
        owner=owner,
        actor=actor,
        is_demo=True,
    )
    places = await _places(session, tree, actor)
    ids: dict[str, Any] = {}
    for p in PEOPLE:
        person = await person_service.create_person(
            session, tree.id, _person_body(p, places), actor
        )
        ids[p.key] = person.id
    await _relations(session, tree.id, ids, places, actor)
    await _stories(session, tree, ids, actor)

    if portraits:
        from app.jobs.queue import enqueue_demo_portraits

        await _portraits(session, storage or get_storage(), tree, ids, actor)
        # One job for all 66 (not 132 separate ones), so a new copy never holds up other
        # people's uploads in the worker.
        await enqueue_demo_portraits(tree.id)
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
                    done = (
                        await complete_demo(session, existing, owner) if existing else DemoUpdate()
                    )
                    print(
                        f"seed: {email} already has {TREE_NAME!r}"
                        + (f"; added {done.added} new people" if done.added else "")
                        + (
                            f"; added biographies / portraits for {done.updated} people"
                            if done.updated
                            else ""
                        )
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
