"""GEDCOM reading: encodings, structure, dates and what the records mean (no database)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.importers.gedcom.dates import parse_date
from app.importers.gedcom.parser import GedcomError, decode, looks_like_gedcom, parse
from app.importers.gedcom.records import read
from tests.gedcom_samples import SAMPLE


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("12 MAR 1890", {"year": 1890, "month": 3, "day": 12, "precision": "exact"}),
        ("MAR 1890", {"year": 1890, "month": 3, "day": None, "precision": "month"}),
        ("1890", {"year": 1890, "month": None, "day": None, "precision": "year"}),
        ("ABT 1850", {"year": 1850, "month": None, "day": None, "precision": "approx"}),
        ("EST 1850", {"year": 1850, "month": None, "day": None, "precision": "approx"}),
        ("BEF 1 JAN 1901", {"year": 1901, "month": 1, "day": 1, "precision": "before"}),
        ("AFT 1945", {"year": 1945, "month": None, "day": None, "precision": "after"}),
        ("11 FEB 1750/51", {"year": 1750, "month": 2, "day": 11, "precision": "exact"}),
        ("@#DJULIAN@ 1 JAN 1700", {"year": 1700, "month": 1, "day": 1, "precision": "exact"}),
    ],
)
def test_dates(value: str, expected: dict[str, object]) -> None:
    assert parse_date(value) == expected


def test_ranges_phrases_and_unreadable_dates() -> None:
    assert parse_date("BET 1914 AND 1918") == {
        "year": 1914,
        "month": None,
        "day": None,
        "end_year": 1918,
        "end_month": None,
        "end_day": None,
        "precision": "between",
    }
    assert parse_date("FROM 1920 TO 1930")["precision"] == "between"  # type: ignore[index]
    assert parse_date("BET 1930 AND 1920") == {
        "precision": "unknown",
        "phrase": "BET 1930 AND 1920",
    }
    assert parse_date("(at Easter)") == {"precision": "unknown", "phrase": "at Easter"}
    assert parse_date("INT 1888 (Easter 1888)") == {
        "year": 1888,
        "month": None,
        "day": None,
        "precision": "year",
        "phrase": "Easter 1888",
    }
    assert parse_date("31 FEB 1900") == {"precision": "unknown", "phrase": "31 FEB 1900"}
    assert parse_date("  ") is None


def test_encodings() -> None:
    text = "0 HEAD\n1 CHAR ANSI\n0 @I1@ INDI\n1 NAME Іван /Коваленко/\n0 TRLR\n"
    assert decode(text.encode("cp1251")) == (text, "Windows-1251")
    assert decode(text.encode("utf-8"))[1] == "UTF-8"
    assert decode(b"\xef\xbb\xbf" + text.encode())[0] == text
    assert decode(text.encode("utf-16"))[0] == text
    western = "0 HEAD\n1 CHAR ANSI\n1 NOTE Müller, Señor\n"
    assert decode(western.encode("cp1252")) == (western, "Windows-1252")
    # ANSEL: the diacritic comes before its letter (0xE8 = diaeresis, 0xB1 = ł).
    ansel = b"0 HEAD\n1 CHAR ANSEL\n1 NOTE M\xe8uller \xb1\xf2odz\n"
    assert decode(ansel) == ("0 HEAD\n1 CHAR ANSEL\n1 NOTE Müller łọdz\n", "ANSEL")


def test_structure() -> None:
    assert looks_like_gedcom(b"\xef\xbb\xbf0 HEAD\r\n1 CHAR UTF-8")
    assert looks_like_gedcom("0 HEAD\n".encode("utf-16"))
    assert not looks_like_gedcom(b"<html>")
    with pytest.raises(GedcomError):
        parse(b"hello\nworld")
    doc = parse(SAMPLE.replace("\n", "\r\n").encode() + b"garbage line\n")
    assert doc.bad_lines == 1
    ivan = next(r for r in doc.of("INDI") if r.xref == "@I1@")
    notes = [n.value for n in ivan.all("NOTE")]
    assert notes[0] == ("Був найкращим ковалем у селі, кував коней для всієї округи.\nДруга лінія.")


def test_records() -> None:
    data = read(parse(SAMPLE.encode()))
    assert data.header == {
        "source": "MyHeritage Family Tree Builder 5.5.1",
        "version": "5.5.1",
        "date": "7 OCT 2026",
    }
    assert len(data.persons) == 4
    ivan = data.persons["@I1@"]
    assert ivan.gender == "male"
    birth, latin = ivan.names
    assert (birth.first_name, birth.patronymic, birth.last_name, birth.script) == (
        "Іван",
        "Петрович",
        "Коваленко",
        "cyrillic",
    )
    assert (latin.first_name, latin.last_name, latin.script) == ("Ivan", "Kovalenko", "latin")
    assert ivan.attributes == {"occupation": "Коваль", "religion": "Православний"}
    assert [e.type for e in ivan.events] == ["birth", "death", "burial", "residence", "custom"]
    assert ivan.vital("death").description == "Cause: Війна"  # type: ignore[union-attr]
    assert ivan.events[-1].title == "Нагорода"
    assert ivan.notes[1] == "Спільна примітка з окремого запису."
    cite = ivan.vital("birth").citations[0]  # type: ignore[union-attr]
    assert (cite.source_xref, cite.page, cite.quality) == ("@S1@", "Арк. 15 зв.", "primary")
    assert data.skipped_tags == {"_CUSTOM": 1}
    assert data.media_links == 1

    hanna = data.persons["@I2@"]
    assert [(n.type, n.last_name) for n in hanna.names] == [
        ("birth", "Мельник"),
        ("married", "Коваленко"),
    ]
    assert data.persons["@I4@"].child_of == [("@F1@", "adoptive")]
    assert data.persons["@I4@"].vital("birth").date == {  # type: ignore[union-attr]
        "precision": "unknown",
        "phrase": "Великдень 1922",
    }

    family = data.families["@F1@"]
    assert (family.husband, family.wife, family.married) == ("@I1@", "@I2@", True)
    assert [c.xref for c in family.children] == ["@I3@", "@I4@"]
    assert family.start_date == {"year": 1915, "month": None, "day": None, "precision": "year"}
    assert family.citations[0].page == "Арк. 3"

    place = data.places["Великі Сорочинці, Полтавська губернія, Російська імперія"]
    assert (place.name, place.region, place.country) == (
        "Великі Сорочинці",
        "Полтавська губернія",
        "Російська імперія",
    )
    assert (place.latitude, place.longitude) == (Decimal("50.024100"), Decimal("33.936800"))
    assert len(data.places) == 2

    source = data.sources["@S1@"]
    assert (source.title, source.archive_name, source.reference_number) == (
        "Метрична книга Преображенської церкви",
        "Державний архів Полтавської області",
        "Ф. 1011, оп. 1, спр. 34",
    )
