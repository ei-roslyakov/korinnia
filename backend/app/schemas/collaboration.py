from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.core.enums import CommentTarget, QuestionStatus, SuggestionStatus, SuggestionTarget
from app.schemas.persons import PersonSummary, Warning
from app.schemas.stories import UserRef


class SuggestionCreate(BaseModel):
    entity_type: SuggestionTarget
    entity_id: uuid.UUID
    # Same shape as PATCH /persons/{id} or PATCH /events/{id}, only the proposed fields.
    patch: dict[str, Any]
    comment: str | None = Field(default=None, max_length=5000)


class SuggestionOut(BaseModel):
    id: uuid.UUID
    entity_type: SuggestionTarget
    entity_id: uuid.UUID
    entity_label: str
    patch: dict[str, Any]
    # Current values of the proposed fields (for a before/after view).
    current: dict[str, Any]
    comment: str | None
    status: SuggestionStatus
    author: UserRef | None
    reviewer: UserRef | None
    review_comment: str | None
    reviewed_at: datetime | None
    created_at: datetime


class CommentCreate(BaseModel):
    entity_type: CommentTarget
    entity_id: uuid.UUID
    body: str = Field(min_length=1, max_length=10_000)


class CommentUpdate(BaseModel):
    body: str = Field(min_length=1, max_length=10_000)


class CommentOut(BaseModel):
    id: uuid.UUID
    entity_type: CommentTarget
    entity_id: uuid.UUID
    body: str
    author: UserRef | None
    created_at: datetime
    updated_at: datetime


class QuestionCreate(BaseModel):
    person_id: uuid.UUID
    question: str = Field(min_length=1, max_length=5000)
    notes: str | None = None


class QuestionUpdate(BaseModel):
    question: str | None = Field(default=None, min_length=1, max_length=5000)
    notes: str | None = None
    status: QuestionStatus | None = None
    resolution: str | None = None


class QuestionOut(BaseModel):
    id: uuid.UUID
    person_id: uuid.UUID
    person_name: str
    question: str
    notes: str | None
    status: QuestionStatus
    resolution: str | None
    resolved_at: datetime | None
    created_by: UserRef | None
    created_at: datetime


class DateProblem(BaseModel):
    person: PersonSummary
    warnings: list[Warning]


class DataQuality(BaseModel):
    """Research to-do list for a tree. Lists are capped at `limit` items each; `counts`
    are exact."""

    counts: dict[str, int]
    missing_birth: list[PersonSummary]
    missing_photo: list[PersonSummary]
    without_sources: list[PersonSummary]
    date_problems: list[DateProblem]
    open_questions: list[QuestionOut]


class ModerationCounts(BaseModel):
    suggestions: int
    stories: int
