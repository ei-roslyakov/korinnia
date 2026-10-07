"""Shared mixins / column helpers for genealogical entities."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, DateTime, ForeignKey, Integer, SmallInteger, String
from sqlalchemy.orm import Mapped, composite, declared_attr, mapped_column

from app.core.dates import PartialDate
from app.core.enums import DatePrecision
from app.models.base import text_enum


class TreeScopedMixin:
    @declared_attr
    def tree_id(cls) -> Mapped[uuid.UUID]:  # noqa: N805
        return mapped_column(ForeignKey("trees.id", ondelete="CASCADE"), index=True)


class AuthoredMixin:
    @declared_attr
    def created_by_id(cls) -> Mapped[uuid.UUID | None]:  # noqa: N805
        return mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    @declared_attr
    def updated_by_id(cls) -> Mapped[uuid.UUID | None]:  # noqa: N805
        return mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class SoftDeleteMixin:
    """Soft delete. Rows deleted together (e.g. a person and their relationships) share a
    `deleted_batch_id`, so restoring the person restores the whole batch."""

    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    deleted_batch_id: Mapped[uuid.UUID | None] = mapped_column(index=True)


def partial_date(prefix: str) -> Any:
    """Composite mapping of a PartialDate onto `<prefix>_year`, `<prefix>_month`, ..."""
    return composite(
        PartialDate,
        mapped_column(f"{prefix}_year", Integer),
        mapped_column(f"{prefix}_month", SmallInteger),
        mapped_column(f"{prefix}_day", SmallInteger),
        mapped_column(f"{prefix}_precision", text_enum(DatePrecision, f"{prefix}_precision")),
        mapped_column(f"{prefix}_end_year", Integer),
        mapped_column(f"{prefix}_end_month", SmallInteger),
        mapped_column(f"{prefix}_end_day", SmallInteger),
        mapped_column(f"{prefix}_phrase", String(200)),
    )


def sort_date_column(prefix: str) -> Mapped[date | None]:
    """Representative date for ordering (derived from the partial date by the service)."""
    return mapped_column(f"{prefix}_sort", Date, index=True)
