from __future__ import annotations

from datetime import date
from typing import Any

import pytest
from pydantic import ValidationError

from app.core.dates import PartialDate, PartialDateError, years_between
from app.models import DatePrecision as P
from app.models import Gender
from app.schemas.dates import PartialDateIn, PartialDateOut
from app.services.genealogy.common import bounds, date_from_dict, date_to_dict
from app.services.genealogy.plausibility import parent_child_warnings, vital_warnings
from app.services.genealogy.vitals import Vitals


@pytest.mark.parametrize(
    ("data", "precision", "text"),
    [
        ({"year": 1890}, P.year, "1890"),
        ({"year": 1902, "month": 3}, P.month, "1902-03"),
        ({"year": 1931, "month": 2, "day": 14}, P.exact, "1931-02-14"),
        ({"year": 1850, "precision": "approx"}, P.approx, "abt 1850"),
        ({"year": 1901, "precision": "before"}, P.before, "bef 1901"),
        ({"year": 1945, "precision": "after"}, P.after, "aft 1945"),
        (
            {"year": 1914, "end_year": 1918, "precision": "between"},
            P.between,
            "bet 1914 and 1918",
        ),
        ({}, P.unknown, ""),
        ({"phrase": "Easter, year unknown"}, P.unknown, "Easter, year unknown"),
    ],
)
def test_partial_date_inference_and_text(data: dict[str, Any], precision: P, text: str) -> None:
    d = PartialDateIn(**data)
    assert d.precision == precision
    assert d.to_domain().to_text() == text


@pytest.mark.parametrize(
    "data",
    [
        {"year": 1900, "month": 2, "day": 30},
        {"year": 1900, "day": 3},
        {"month": 3},
        {"year": 1900, "precision": "exact"},
        {"year": 1900, "month": 3, "precision": "year"},
        {"year": 1900, "month": 3, "day": 1, "precision": "month"},
        {"year": 1914, "precision": "between"},
        {"year": 1918, "end_year": 1914, "precision": "between"},
        {"year": 1900, "end_year": 1910, "precision": "approx"},
        {"precision": "approx"},
        {"year": 1900, "precision": "unknown"},
        {"year": 1900, "end_month": 13},
    ],
)
def test_invalid_partial_dates(data: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        PartialDateIn(**data)


def test_domain_validation_errors() -> None:
    with pytest.raises(PartialDateError):
        PartialDate(year=0, precision=P.year).validate()
    with pytest.raises(PartialDateError):
        PartialDate(year=1900, precision=P.unknown, end_year=1901).validate()


def test_sort_keys_and_bounds() -> None:
    d = PartialDate(year=1902, month=3, precision=P.month)
    assert d.sort_key() == date(1902, 3, 1)
    assert d.end_sort_key() == date(1902, 3, 31)
    assert bounds(PartialDate(year=1900, precision=P.before)) == (None, date(1900, 1, 1))
    assert bounds(PartialDate(year=1900, precision=P.after)) == (date(1900, 1, 1), None)
    lo, hi = bounds(PartialDate(year=1900, precision=P.approx))
    assert lo is not None
    assert lo.year == 1895
    assert hi is not None
    assert hi.year == 1905
    assert bounds(None) == (None, None)
    assert bounds(PartialDate()) == (None, None)
    assert PartialDate().sort_key() is None
    assert PartialDate().end_sort_key() is None


def test_date_dict_roundtrip_and_out() -> None:
    d = PartialDate(year=1914, end_year=1918, precision=P.between, phrase="WWI")
    assert date_from_dict(date_to_dict(d)) == d
    assert date_to_dict(PartialDate()) is None
    assert date_from_dict(None) == PartialDate()
    out = PartialDateOut.from_domain(d)
    assert out is not None
    assert out.text == "bet 1914 and 1918"
    assert PartialDateOut.from_domain(PartialDate()) is None


def test_years_between() -> None:
    assert years_between(date(1900, 6, 1), date(1950, 5, 31)) == 49
    assert years_between(date(1900, 6, 1), date(1950, 6, 1)) == 50


class _Ev:
    def __init__(self, d: PartialDate) -> None:
        self.date = d


def _vitals(birth: PartialDate | None = None, death: PartialDate | None = None) -> Vitals:
    return Vitals(
        birth=_Ev(birth) if birth else None,  # type: ignore[arg-type]
        death=_Ev(death) if death else None,  # type: ignore[arg-type]
    )


def y(year: int, precision: P = P.year) -> PartialDate:
    return PartialDate(year=year, precision=precision)


def test_vital_warnings() -> None:
    def codes(v: Vitals, living: bool = False) -> list[str]:
        return [w.code for w in vital_warnings(v, is_living=living)]

    assert codes(_vitals(y(1900), y(1890))) == ["death_before_birth"]
    assert codes(_vitals(y(1800), y(1950))) == ["lifespan_too_long"]
    assert codes(_vitals(y(1850)), living=True) == ["living_too_old"]
    assert codes(_vitals(y(1900, P.approx), y(1898))) == []  # approx gives slack
    assert codes(_vitals(None, y(1900))) == []


def test_parent_child_warnings() -> None:
    import uuid

    pid = uuid.uuid4()

    def codes(parent: Vitals, child: Vitals, gender: Gender = Gender.male) -> list[str]:
        return [w.code for w in parent_child_warnings(parent, gender, child, parent_id=pid)]

    assert codes(_vitals(y(1900)), _vitals(y(1890))) == ["child_born_before_parent"]
    assert codes(_vitals(y(1900)), _vitals(y(1908))) == ["parent_too_young"]
    assert codes(_vitals(y(1800)), _vitals(y(1895)), Gender.male) == ["parent_too_old"]
    assert codes(_vitals(y(1830)), _vitals(y(1895)), Gender.female) == ["parent_too_old"]
    assert codes(_vitals(y(1860), y(1880)), _vitals(y(1885)), Gender.female) == [
        "born_after_parent_death"
    ]
    # Father may die before the child is born (up to ~10 months).
    father = _vitals(y(1860), PartialDate(year=1900, month=1, day=10, precision=P.exact))
    child = _vitals(PartialDate(year=1900, month=8, day=1, precision=P.exact))
    assert codes(father, child) == []
    assert codes(_vitals(y(1870)), _vitals(y(1895))) == []
