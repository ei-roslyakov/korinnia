from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.core.enums import StoryKind, StoryStatus
from app.schemas.dates import PartialDateIn, PartialDateOut
from app.schemas.media import MediaOut
from app.schemas.persons import PersonSummary


class Ingredient(BaseModel):
    amount: str | None = Field(default=None, max_length=100)  # "2 cups", "a pinch"
    item: str = Field(min_length=1, max_length=300)


class Recipe(BaseModel):
    """The structured part of a family recipe; the story behind it is the Markdown body."""

    servings: int | None = Field(default=None, ge=1, le=1000)
    prep_minutes: int | None = Field(default=None, ge=0, le=100_000)
    cook_minutes: int | None = Field(default=None, ge=0, le=100_000)
    ingredients: list[Ingredient] = Field(default_factory=list, max_length=200)
    steps: list[str] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def _clean_steps(self) -> Recipe:
        self.steps = [s.strip() for s in self.steps if s.strip()]
        if any(len(s) > 5000 for s in self.steps):
            raise ValueError("a step is at most 5000 characters")
        return self


class StoryFields(BaseModel):
    body: str | None = None
    recipe: Recipe | None = None
    occasion: str | None = Field(default=None, max_length=200)
    narrator: str | None = Field(default=None, max_length=300)
    date: PartialDateIn | None = None
    person_ids: list[uuid.UUID] | None = Field(default=None, max_length=500)
    media_ids: list[uuid.UUID] | None = Field(default=None, max_length=500)


class StoryCreate(StoryFields):
    title: str = Field(min_length=1, max_length=300)
    # Editors may publish directly; contributors' stories always start as drafts.
    status: StoryStatus = StoryStatus.draft
    kind: StoryKind = StoryKind.story

    @model_validator(mode="after")
    def _recipe_only_for_recipes(self) -> StoryCreate:
        if self.recipe is not None and self.kind != StoryKind.recipe:
            raise ValueError("only a recipe has ingredients and steps")
        return self


class StoryUpdate(StoryFields):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    kind: StoryKind | None = None


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
    kind: StoryKind = StoryKind.story
    occasion: str | None = None
    # Thumbnail of the story's first photo or scan, for the story list.
    cover_url: str | None = None
    reading_minutes: int = 1


class StoryOut(StorySummary):
    body: str
    recipe: Recipe | None = None
    persons: list[PersonSummary]
    media: list[MediaOut]
    review_comment: str | None
    can_edit: bool
    created_at: datetime
