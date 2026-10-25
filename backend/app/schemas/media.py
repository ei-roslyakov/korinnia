from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.core.enums import MediaKind, ProcessingStatus
from app.schemas.common import Page
from app.schemas.dates import PartialDateIn, PartialDateOut
from app.schemas.places import PlaceSummary


class Region(BaseModel):
    """Rectangle as fractions (0..1) of the image width/height, from the top-left corner."""

    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    w: float = Field(gt=0, le=1)
    h: float = Field(gt=0, le=1)

    @model_validator(mode="after")
    def _inside(self) -> Region:
        if self.x + self.w > 1.0001 or self.y + self.h > 1.0001:
            raise ValueError("region must lie inside the image")
        return self


class MediaPersonOut(BaseModel):
    person_id: uuid.UUID
    display_name: str
    region: Region | None


class MediaUrls(BaseModel):
    original: str
    web: str
    thumb: str | None


class MediaOut(BaseModel):
    id: uuid.UUID
    kind: MediaKind
    title: str | None
    description: str | None
    date: PartialDateOut | None
    place: PlaceSummary | None
    original_filename: str
    mime_type: str
    size: int
    sha256: str
    width: int | None
    height: int | None
    duration_seconds: float | None
    processing_status: ProcessingStatus
    processing_error: str | None
    urls: MediaUrls
    people: list[MediaPersonOut]
    created_at: datetime


class AlbumPage(Page[MediaOut]):
    # Decades (1950 = the 1950s) that have dated photos, for the album's filter.
    decades: list[int]


class MediaUpdate(BaseModel):
    kind: MediaKind | None = None
    title: str | None = Field(default=None, max_length=300)
    description: str | None = None
    date: PartialDateIn | None = None
    place_id: uuid.UUID | None = None


class TagIn(BaseModel):
    person_id: uuid.UUID
    region: Region | None = None


class TagUpdate(BaseModel):
    region: Region | None = None


class MediaOrder(BaseModel):
    media_ids: list[uuid.UUID] = Field(max_length=5000)
