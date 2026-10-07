from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import Schema


class HistoricalName(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    from_year: int | None = Field(default=None, ge=1, le=9999)
    until_year: int | None = Field(default=None, ge=1, le=9999)
    note: str | None = Field(default=None, max_length=1000)


class PlaceFields(BaseModel):
    historical_names: list[HistoricalName] = Field(default_factory=list, max_length=50)
    country: str | None = Field(default=None, max_length=100)
    region: str | None = Field(default=None, max_length=200)
    latitude: Decimal | None = Field(default=None, ge=-90, le=90, decimal_places=6)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180, decimal_places=6)
    notes: str | None = None

    @model_validator(mode="after")
    def _coordinates_together(self) -> PlaceFields:
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be given together")
        return self


class PlaceCreate(PlaceFields):
    name: str = Field(min_length=1, max_length=300)


class PlaceUpdate(PlaceFields):
    name: str | None = Field(default=None, min_length=1, max_length=300)
    historical_names: list[HistoricalName] | None = Field(default=None, max_length=50)  # type: ignore[assignment]


class PlaceSummary(Schema):
    id: uuid.UUID
    name: str
    country: str | None
    region: str | None
    latitude: Decimal | None
    longitude: Decimal | None


class PlaceOut(PlaceSummary):
    historical_names: list[HistoricalName]
    notes: str | None
    created_at: datetime
    updated_at: datetime
