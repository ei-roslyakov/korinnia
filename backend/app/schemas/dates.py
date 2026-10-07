from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field, model_validator

from app.core.dates import PartialDate, PartialDateError
from app.core.enums import DatePrecision


class PartialDateIn(BaseModel):
    """A possibly incomplete date. If `precision` is omitted it is inferred:
    year+month+day → exact, year+month → month, year → year, nothing → unknown."""

    year: int | None = Field(default=None, ge=1, le=9999)
    month: int | None = Field(default=None, ge=1, le=12)
    day: int | None = Field(default=None, ge=1, le=31)
    precision: DatePrecision | None = None
    end_year: int | None = Field(default=None, ge=1, le=9999)
    end_month: int | None = Field(default=None, ge=1, le=12)
    end_day: int | None = Field(default=None, ge=1, le=31)
    phrase: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def _validate(self) -> PartialDateIn:
        if self.precision is None:
            if self.year is None:
                self.precision = DatePrecision.unknown
            elif self.day is not None:
                self.precision = DatePrecision.exact
            elif self.month is not None:
                self.precision = DatePrecision.month
            else:
                self.precision = DatePrecision.year
        try:
            self.to_domain().validate()
        except PartialDateError as exc:
            raise ValueError(str(exc)) from exc
        return self

    def to_domain(self) -> PartialDate:
        return PartialDate(
            year=self.year,
            month=self.month,
            day=self.day,
            precision=self.precision,
            end_year=self.end_year,
            end_month=self.end_month,
            end_day=self.end_day,
            phrase=self.phrase or None,
        )


class PartialDateOut(BaseModel):
    year: int | None
    month: int | None
    day: int | None
    precision: DatePrecision | None
    end_year: int | None
    end_month: int | None
    end_day: int | None
    phrase: str | None
    text: str
    sort: dt.date | None

    @classmethod
    def from_domain(cls, d: PartialDate | None) -> PartialDateOut | None:
        if d is None or d.is_empty:
            return None
        return cls(
            year=d.year,
            month=d.month,
            day=d.day,
            precision=d.precision,
            end_year=d.end_year,
            end_month=d.end_month,
            end_day=d.end_day,
            phrase=d.phrase,
            text=d.to_text(),
            sort=d.sort_key(),
        )
