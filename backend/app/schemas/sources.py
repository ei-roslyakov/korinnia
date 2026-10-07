from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.core.enums import CitationQuality, CitedEntity, SourceType
from app.schemas.media import MediaOut


def _check_url(v: str | None) -> str | None:
    if v and not v.lower().startswith(("http://", "https://")):
        raise ValueError("url must start with http:// or https://")
    return v or None


class SourceFields(BaseModel):
    author: str | None = Field(default=None, max_length=300)
    archive_name: str | None = Field(default=None, max_length=300)
    reference_number: str | None = Field(default=None, max_length=300)
    url: str | None = Field(default=None, max_length=2000)
    notes: str | None = None
    media_ids: list[uuid.UUID] | None = Field(default=None, max_length=200)

    _url = field_validator("url")(_check_url)


class SourceCreate(SourceFields):
    title: str = Field(min_length=1, max_length=500)
    type: SourceType = SourceType.other


class SourceUpdate(SourceFields):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    type: SourceType | None = None


class SourceSummary(BaseModel):
    id: uuid.UUID
    title: str
    type: SourceType


class SourceOut(SourceSummary):
    author: str | None
    archive_name: str | None
    reference_number: str | None
    url: str | None
    notes: str | None
    media: list[MediaOut]
    citation_count: int
    created_at: datetime
    updated_at: datetime


class CitationFields(BaseModel):
    field: str | None = Field(default=None, max_length=100)
    page: str | None = Field(default=None, max_length=300)
    quality: CitationQuality | None = None
    notes: str | None = None


class CitationCreate(CitationFields):
    source_id: uuid.UUID
    entity_type: CitedEntity
    entity_id: uuid.UUID


class CitationUpdate(CitationFields):
    pass


class CitationTarget(BaseModel):
    """What the citation supports, with a neutral label (codes, not translated text):
    e.g. kind="event", event_type="birth", date="1923-02-14"."""

    entity_type: CitedEntity
    entity_id: uuid.UUID
    event_type: str | None = None
    date: str | None = None
    label: str | None = None


class CitationOut(BaseModel):
    id: uuid.UUID
    source: SourceSummary
    target: CitationTarget
    field: str | None
    page: str | None
    quality: CitationQuality
    notes: str | None
    created_at: datetime
