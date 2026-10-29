from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.core.enums import (
    Gender,
    NameType,
    ParentChildType,
    PartnershipEndReason,
    PartnershipType,
    ResearchStatus,
    Script,
)
from app.schemas.dates import PartialDateIn, PartialDateOut
from app.schemas.events import EventOut
from app.schemas.media import MediaOut, Region
from app.schemas.places import PlaceSummary


class NameIn(BaseModel):
    type: NameType = NameType.birth
    first_name: str | None = Field(default=None, max_length=200)
    middle_name: str | None = Field(default=None, max_length=200)
    patronymic: str | None = Field(default=None, max_length=200)
    last_name: str | None = Field(default=None, max_length=200)
    maiden_name: str | None = Field(default=None, max_length=200)
    script: Script = Script.cyrillic
    is_primary: bool = False
    notes: str | None = None

    @model_validator(mode="after")
    def _not_empty(self) -> NameIn:
        if not any(
            (v or "").strip()
            for v in (
                self.first_name,
                self.middle_name,
                self.patronymic,
                self.last_name,
                self.maiden_name,
            )
        ):
            raise ValueError("a name needs at least one part")
        return self


class NameOut(NameIn):
    id: uuid.UUID
    display: str


class VitalIn(BaseModel):
    """Birth or death, exposed as a first-class field (stored as an Event)."""

    date: PartialDateIn | None = None
    place_id: uuid.UUID | None = None
    description: str | None = None


class VitalOut(BaseModel):
    event_id: uuid.UUID
    date: PartialDateOut | None
    place: PlaceSummary | None
    description: str | None


class PersonFields(BaseModel):
    primary_photo_id: uuid.UUID | None = None
    primary_photo_crop: Region | None = None
    gender: Gender | None = None
    is_living: bool | None = None
    short_summary: str | None = Field(default=None, max_length=500)
    biography: str | None = None
    occupation: str | None = None
    education: str | None = None
    religion: str | None = Field(default=None, max_length=200)
    nationality: str | None = Field(default=None, max_length=200)
    notes_for_descendants: str | None = None
    research_status: ResearchStatus | None = None
    birth: VitalIn | None = None
    death: VitalIn | None = None


def _check_names(names: list[NameIn] | None) -> None:
    if names and sum(n.is_primary for n in names) > 1:
        raise ValueError("only one name can be primary")


class RelativeLink(BaseModel):
    """Link the new person to an existing one in the same request (atomically).

    - parent:  new person becomes a parent of `person_id`; with `other_parent_id` (an
      existing parent of `person_id`) the two parents also become partners.
    - child:   new person becomes a child of `person_id` (and of `other_parent_id`).
    - partner: new partnership between `person_id` and the new person.
    - sibling: new person gets the same parents as `person_id`.
    """

    person_id: uuid.UUID
    relation: Literal["parent", "child", "partner", "sibling"]
    parent_child_type: ParentChildType = ParentChildType.biological
    partnership_type: PartnershipType = PartnershipType.marriage
    other_parent_id: uuid.UUID | None = None


class PersonCreate(PersonFields):
    names: list[NameIn] = Field(default_factory=list, max_length=50)
    relative: RelativeLink | None = None

    @model_validator(mode="after")
    def _names(self) -> PersonCreate:
        _check_names(self.names)
        return self


class PersonUpdate(PersonFields):
    """Partial update. `names`, if given, replaces all names. `birth`/`death` set to null
    removes the record."""

    names: list[NameIn] | None = Field(default=None, max_length=50)

    @model_validator(mode="after")
    def _names(self) -> PersonUpdate:
        _check_names(self.names)
        return self


class LifeSpan(BaseModel):
    birth: PartialDateOut | None
    death: PartialDateOut | None


class PersonSummary(BaseModel):
    id: uuid.UUID
    display_name: str
    gender: Gender
    is_living: bool
    birth: PartialDateOut | None
    death: PartialDateOut | None
    birth_place: str | None = None
    primary_photo_id: uuid.UUID | None = None
    avatar_url: str | None = None
    # Only the basics of this living person are shown to this reader (D114).
    details_hidden: bool = False


class ParentRef(BaseModel):
    relationship_id: uuid.UUID
    type: ParentChildType
    person: PersonSummary


class PartnerRef(BaseModel):
    partnership_id: uuid.UUID
    type: PartnershipType
    start_date: PartialDateOut | None
    end_date: PartialDateOut | None
    end_reason: PartnershipEndReason | None
    person: PersonSummary


class SiblingRef(BaseModel):
    half: bool
    person: PersonSummary


class Warning(BaseModel):
    code: str
    params: dict[str, Any] = Field(default_factory=dict)


class PersonDetail(BaseModel):
    id: uuid.UUID
    tree_id: uuid.UUID
    display_name: str
    gender: Gender
    is_living: bool
    short_summary: str | None
    biography: str | None
    occupation: str | None
    education: str | None
    religion: str | None
    nationality: str | None
    notes_for_descendants: str | None
    research_status: ResearchStatus
    primary_photo_id: uuid.UUID | None
    primary_photo_crop: Region | None
    avatar_url: str | None
    # The cropped portrait is being rendered by the worker (avatar_url is a fallback).
    portrait_pending: bool
    media: list[MediaOut]
    names: list[NameOut]
    birth: VitalOut | None
    death: VitalOut | None
    events: list[EventOut]
    parents: list[ParentRef]
    children: list[ParentRef]
    partners: list[PartnerRef]
    siblings: list[SiblingRef]
    warnings: list[Warning]
    created_at: datetime
    updated_at: datetime
    # Only the basics of this living person are shown to this reader (D114).
    details_hidden: bool = False


class DeletePreview(BaseModel):
    person: PersonSummary
    parent_links: int
    child_links: int
    partnerships: int
    events: int
    shared_events: int
