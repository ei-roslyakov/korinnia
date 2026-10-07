from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.core.enums import StoryStatus
from app.schemas.dates import PartialDateIn, PartialDateOut
from app.schemas.media import MediaOut
from app.schemas.persons import PersonSummary


class StoryFields(BaseModel):
    body: str | None = None
    narrator: str | None = Field(default=None, max_length=300)
    date: PartialDateIn | None = None
    person_ids: list[uuid.UUID] | None = Field(default=None, max_length=500)
    media_ids: list[uuid.UUID] | None = Field(default=None, max_length=500)


class StoryCreate(StoryFields):
    title: str = Field(min_length=1, max_length=300)
    # Editors may publish directly; contributors' stories always start as drafts.
    status: StoryStatus = StoryStatus.draft


class StoryUpdate(StoryFields):
    title: str | None = Field(default=None, min_length=1, max_length=300)


class ReviewIn(BaseModel):
    comment: str | None = Field(default=None, max_length=5000)


class UserRef(BaseModel):
    id: uuid.UUID
    display_name: str


class StorySummary(BaseModel):
    id: uuid.UUID
    title: str
    excerpt: str
    narrator: str | None
    date: PartialDateOut | None
    status: StoryStatus
    author: UserRef | None
    person_ids: list[uuid.UUID]
    updated_at: datetime
    # Thumbnail of the story's first photo or scan, for the story list.
    cover_url: str | None = None
    reading_minutes: int = 1


class StoryOut(StorySummary):
    body: str
    persons: list[PersonSummary]
    media: list[MediaOut]
    review_comment: str | None
    can_edit: bool
    created_at: datetime
