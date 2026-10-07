from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from app.core.enums import EventType, ParticipantRole
from app.schemas.dates import PartialDateIn, PartialDateOut
from app.schemas.places import PlaceSummary


class ParticipantIn(BaseModel):
    person_id: uuid.UUID
    role: ParticipantRole = ParticipantRole.principal


class EventFields(BaseModel):
    title: str | None = Field(default=None, max_length=300)
    description: str | None = None
    date: PartialDateIn | None = None
    place_id: uuid.UUID | None = None
    cemetery_name: str | None = Field(default=None, max_length=300)
    burial_plot: str | None = Field(default=None, max_length=200)
    latitude: Decimal | None = Field(default=None, ge=-90, le=90, decimal_places=6)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180, decimal_places=6)

    @model_validator(mode="after")
    def _coordinates_together(self) -> EventFields:
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be given together")
        return self


class EventCreate(EventFields):
    type: EventType
    participants: list[ParticipantIn] = Field(min_length=1, max_length=50)


class EventUpdate(EventFields):
    type: EventType | None = None
    participants: list[ParticipantIn] | None = Field(default=None, min_length=1, max_length=50)


class ParticipantOut(BaseModel):
    person_id: uuid.UUID
    role: ParticipantRole
    display_name: str


class EventOut(BaseModel):
    id: uuid.UUID
    type: EventType
    title: str | None
    description: str | None
    date: PartialDateOut | None
    place: PlaceSummary | None
    cemetery_name: str | None
    burial_plot: str | None
    latitude: Decimal | None
    longitude: Decimal | None
    participants: list[ParticipantOut]
    created_at: datetime
    updated_at: datetime
