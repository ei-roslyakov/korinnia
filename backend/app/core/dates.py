"""Genealogical partial dates (see docs/decisions.md D2).

A PartialDate records only what is actually known: "1890", "March 1902", "about 1850",
"before 1901", "between 1914 and 1918". Nothing is invented: a year-only date stores no
month or day. `sort_key()` gives a real `date` for ordering and age arithmetic.
"""

# No `from __future__ import annotations`: SQLAlchemy's composite() reads the dataclass
# field annotations at runtime.

import calendar
from dataclasses import dataclass
from datetime import date

from app.core.enums import DatePrecision

# Precisions that are anchored on a single (possibly partial) date.
_SINGLE = {
    DatePrecision.exact,
    DatePrecision.month,
    DatePrecision.year,
    DatePrecision.approx,
    DatePrecision.before,
    DatePrecision.after,
}


class PartialDateError(ValueError):
    pass


def _check_ymd(year: int | None, month: int | None, day: int | None, label: str) -> None:
    if year is None:
        if month is not None or day is not None:
            raise PartialDateError(f"{label}: month/day given without a year")
        return
    if not 1 <= year <= 9999:
        raise PartialDateError(f"{label}: year out of range")
    if month is None:
        if day is not None:
            raise PartialDateError(f"{label}: day given without a month")
        return
    if not 1 <= month <= 12:
        raise PartialDateError(f"{label}: month out of range")
    if day is not None and not 1 <= day <= calendar.monthrange(year, month)[1]:
        raise PartialDateError(f"{label}: day out of range")


@dataclass(frozen=True, slots=True)
class PartialDate:
    year: int | None = None
    month: int | None = None
    day: int | None = None
    precision: DatePrecision | None = None
    end_year: int | None = None
    end_month: int | None = None
    end_day: int | None = None
    # Free-text original wording, e.g. "Easter 1888" or a GEDCOM date phrase.
    phrase: str | None = None

    @property
    def is_empty(self) -> bool:
        return (
            self.year is None
            and not self.phrase
            and self.precision
            in (
                None,
                DatePrecision.unknown,
            )
        )

    def validate(self) -> PartialDate:
        p = self.precision
        _check_ymd(self.year, self.month, self.day, "date")
        _check_ymd(self.end_year, self.end_month, self.end_day, "end date")
        if p is None or p == DatePrecision.unknown:
            if self.year is not None or self.end_year is not None:
                raise PartialDateError("unknown date must not have a year")
            return self
        if self.year is None:
            raise PartialDateError(f"precision {p.value!r} requires a year")
        if p == DatePrecision.exact and (self.month is None or self.day is None):
            raise PartialDateError("exact date requires year, month and day")
        if p == DatePrecision.month and (self.month is None or self.day is not None):
            raise PartialDateError("month precision requires year and month, no day")
        if p == DatePrecision.year and self.month is not None:
            raise PartialDateError("year precision must not have month or day")
        if p == DatePrecision.between:
            if self.end_year is None:
                raise PartialDateError("between requires an end year")
            if self.end_sort_key() < self.start_sort_key():  # type: ignore[operator]
                raise PartialDateError("end of range is before its start")
        elif p in _SINGLE and self.end_year is not None:
            raise PartialDateError(f"precision {p.value!r} must not have an end date")
        return self

    def start_sort_key(self) -> date | None:
        if self.year is None:
            return None
        return date(self.year, self.month or 1, self.day or 1)

    def end_sort_key(self) -> date | None:
        """Latest possible date covered (end of range / month / year)."""
        y, m, d = (
            (self.end_year, self.end_month, self.end_day)
            if self.precision == DatePrecision.between
            else (self.year, self.month, self.day)
        )
        if y is None:
            return None
        m_ = m or 12
        return date(y, m_, d or calendar.monthrange(y, m_)[1])

    def sort_key(self) -> date | None:
        """Representative date used for ordering timelines."""
        return self.start_sort_key()

    def to_text(self) -> str:
        """Neutral ISO-like rendering, e.g. 'abt 1850', '1902-03', 'bet 1914 and 1918'."""
        if self.year is None:
            return self.phrase or ""

        def fmt(y: int, m: int | None, d: int | None) -> str:
            return f"{y:04d}" + (f"-{m:02d}" if m else "") + (f"-{d:02d}" if d else "")

        base = fmt(self.year, self.month, self.day)
        match self.precision:
            case DatePrecision.approx:
                return f"abt {base}"
            case DatePrecision.before:
                return f"bef {base}"
            case DatePrecision.after:
                return f"aft {base}"
            case DatePrecision.between:
                assert self.end_year is not None
                return f"bet {base} and {fmt(self.end_year, self.end_month, self.end_day)}"
            case _:
                return base


def years_between(earlier: date, later: date) -> int:
    """Whole years from `earlier` to `later` (negative if `later` is earlier)."""
    years = later.year - earlier.year
    if (later.month, later.day) < (earlier.month, earlier.day):
        years -= 1
    return years
