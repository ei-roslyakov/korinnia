"""Shared helpers for genealogy services."""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dates import PartialDate
from app.core.errors import AppError, NotFoundError
from app.models import DatePrecision, Person, PersonName, Place
from app.schemas.dates import PartialDateIn

# How much an "approximate" date may be off when checking plausibility.
APPROX_TOLERANCE = timedelta(days=5 * 365)
EMPTY_DATE = PartialDate()


async def get_live[T](
    session: AsyncSession, model: type[T], tree_id: uuid.UUID, entity_id: uuid.UUID, code: str
) -> T:
    """Load a non-deleted entity of the given tree or raise 404 with `code`."""
    obj = await session.get(model, entity_id)
    if (
        obj is None
        or getattr(obj, "tree_id", None) != tree_id
        or getattr(obj, "deleted_at", None) is not None
    ):
        raise NotFoundError(code)
    return obj


async def check_place(
    session: AsyncSession, tree_id: uuid.UUID, place_id: uuid.UUID | None
) -> Place | None:
    if place_id is None:
        return None
    place = await session.get(Place, place_id)
    if place is None or place.tree_id != tree_id or place.deleted_at is not None:
        raise AppError("invalid_place")
    return place


async def check_persons(
    session: AsyncSession, tree_id: uuid.UUID, person_ids: Iterable[uuid.UUID]
) -> None:
    ids = set(person_ids)
    if not ids:
        return
    found = set(
        await session.scalars(
            select(Person.id).where(
                Person.id.in_(ids), Person.tree_id == tree_id, Person.deleted_at.is_(None)
            )
        )
    )
    if found != ids:
        raise NotFoundError("person_not_found")


def to_partial(value: PartialDateIn | None) -> PartialDate:
    return value.to_domain() if value is not None else EMPTY_DATE


def set_date(obj: Any, attr: str, sort_attr: str, value: PartialDate) -> None:
    setattr(obj, attr, value)
    setattr(obj, sort_attr, value.sort_key())


def date_to_dict(d: PartialDate | None) -> dict[str, Any] | None:
    if d is None or d.is_empty:
        return None
    return {
        "year": d.year,
        "month": d.month,
        "day": d.day,
        "precision": d.precision.value if d.precision else None,
        "end_year": d.end_year,
        "end_month": d.end_month,
        "end_day": d.end_day,
        "phrase": d.phrase,
    }


def date_from_dict(data: dict[str, Any] | None) -> PartialDate:
    if not data:
        return EMPTY_DATE
    return PartialDate(
        year=data.get("year"),
        month=data.get("month"),
        day=data.get("day"),
        precision=DatePrecision(data["precision"]) if data.get("precision") else None,
        end_year=data.get("end_year"),
        end_month=data.get("end_month"),
        end_day=data.get("end_day"),
        phrase=data.get("phrase"),
    )


def bounds(d: PartialDate | None) -> tuple[date | None, date | None]:
    """Earliest and latest dates a partial date can mean (None = open-ended)."""
    if d is None or d.year is None or d.precision in (None, DatePrecision.unknown):
        return None, None
    lo, hi = d.start_sort_key(), d.end_sort_key()
    match d.precision:
        case DatePrecision.approx:
            assert lo is not None
            assert hi is not None
            return lo - APPROX_TOLERANCE, hi + APPROX_TOLERANCE
        case DatePrecision.before:
            return None, lo
        case DatePrecision.after:
            return lo, None
        case _:
            return lo, hi


def name_display(name: PersonName | None) -> str:
    if name is None:
        return "?"
    parts = [name.first_name, name.middle_name, name.patronymic, name.last_name]
    text = " ".join(p.strip() for p in parts if p and p.strip())
    if name.maiden_name and name.maiden_name != name.last_name:
        text = f"{text} ({name.maiden_name})" if text else name.maiden_name
    return text or "?"


def pick_primary(names: Iterable[PersonName]) -> PersonName | None:
    ordered = sorted(names, key=lambda n: (not n.is_primary, n.sort_order))
    return ordered[0] if ordered else None
