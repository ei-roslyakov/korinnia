"""A place's page: who was born, lived, married, died or is buried there (D116)."""

from __future__ import annotations

import uuid

from pydantic import BaseModel

from app.schemas.insights import Fact
from app.schemas.media import MediaOut
from app.schemas.persons import PersonSummary
from app.schemas.places import PlaceOut, PlaceSummary
from app.schemas.stories import StorySummary


class PlaceIndexItem(BaseModel):
    place: PlaceOut
    events: int  # facts (events and marriages) at the place
    people: int  # different people in them


class NearbyPlace(BaseModel):
    place: PlaceSummary
    distance_km: float


class PlacePage(BaseModel):
    place: PlaceOut
    # Facts by type ("birth", "residence", "marriage", …).
    counts: dict[str, int]
    # Facts at the place in date order (undated last), with their people and roles.
    facts: list[Fact]
    persons: list[PersonSummary]
    media: list[MediaOut]
    # Stories whose title or text mentions one of the place's names.
    stories: list[StorySummary]
    nearby: list[NearbyPlace]


class PlaceMergeIn(BaseModel):
    target_id: uuid.UUID
