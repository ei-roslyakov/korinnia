from __future__ import annotations

import pytest

from app.services.search_text import (
    build_search_text,
    normalize,
    query_alternatives,
    transliterate_uk,
)


@pytest.mark.parametrize(
    ("cyrillic", "latin"),
    [
        ("Коваленко", "kovalenko"),
        ("Олександр", "oleksandr"),
        ("Юрій", "yurii"),
        ("Їжакевич", "yizhakevych"),
        ("Знам'янка", "znamianka"),
        ("Згурський", "zghurskyi"),
        ("Щербак", "shcherbak"),
        ("Яготин", "yahotyn"),
        ("Ґалаґан", "galagan"),
        ("Феодосія", "feodosiia"),
        ("Halyna", "halyna"),
    ],
)
def test_transliterate_kmu2010(cyrillic: str, latin: str) -> None:
    assert transliterate_uk(cyrillic) == latin


def test_normalize() -> None:
    assert normalize("Ołeńka O’Neil") == "ołenka oneil"


def test_build_search_text_dedupes_and_mixes_scripts() -> None:
    text = build_search_text(["Галина", None, "Коваленко", "Halyna"])
    assert text.split() == ["галина", "halyna", "коваленко", "kovalenko"]


def test_query_alternatives() -> None:
    assert query_alternatives("Ковал Gal") == [["koval", "ковал"], ["gal"]]
    assert query_alternatives("  ") == []
