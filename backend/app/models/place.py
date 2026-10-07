"""Places, including their historical names (e.g. Stanislaviv → Ivano-Frankivsk)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import CheckConstraint, Index, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.genealogy_base import AuthoredMixin, SoftDeleteMixin, TreeScopedMixin


class Place(
    UUIDPrimaryKeyMixin, TreeScopedMixin, AuthoredMixin, SoftDeleteMixin, TimestampMixin, Base
):
    __tablename__ = "places"
    __table_args__ = (
        CheckConstraint("latitude BETWEEN -90 AND 90", name="latitude_range"),
        CheckConstraint("longitude BETWEEN -180 AND 180", name="longitude_range"),
        Index(
            "ix_places_search_text_trgm",
            "search_text",
            postgresql_using="gin",
            postgresql_ops={"search_text": "gin_trgm_ops"},
        ),
    )

    # Current / commonly used name.
    name: Mapped[str] = mapped_column(String(300))
    # [{"name": "Stanislaviv", "until_year": 1962, "note": "..."}, ...]
    historical_names: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    country: Mapped[str | None] = mapped_column(String(100))
    region: Mapped[str | None] = mapped_column(String(200))
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    notes: Mapped[str | None] = mapped_column(Text)
    # Normalised name + historical names + transliterations, for fuzzy search.
    search_text: Mapped[str] = mapped_column(Text, default="", server_default="")
