from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.core.enums import ParentChildType, PartnershipEndReason, PartnershipType
from app.schemas.dates import PartialDateIn, PartialDateOut
from app.schemas.persons import PersonSummary, Warning
from app.schemas.places import PlaceSummary


class ParentChildCreate(BaseModel):
    parent_id: uuid.UUID
    child_id: uuid.UUID
    type: ParentChildType = ParentChildType.biological
    notes: str | None = None


class ParentChildUpdate(BaseModel):
    type: ParentChildType | None = None
    notes: str | None = None


class ParentChildOut(BaseModel):
    id: uuid.UUID
    parent_id: uuid.UUID
    child_id: uuid.UUID
    type: ParentChildType
    notes: str | None
    created_at: datetime
    warnings: list[Warning] = Field(default_factory=list)


class PartnershipFields(BaseModel):
    type: PartnershipType | None = None
    start_date: PartialDateIn | None = None
    end_date: PartialDateIn | None = None
    end_reason: PartnershipEndReason | None = None
    place_id: uuid.UUID | None = None
    notes: str | None = None


class PartnershipCreate(PartnershipFields):
    person_a_id: uuid.UUID
    person_b_id: uuid.UUID


class PartnershipUpdate(PartnershipFields):
    pass


class PartnershipOut(BaseModel):
    id: uuid.UUID
    person_a_id: uuid.UUID
    person_b_id: uuid.UUID
    type: PartnershipType
    start_date: PartialDateOut | None
    end_date: PartialDateOut | None
    end_reason: PartnershipEndReason | None
    place: PlaceSummary | None
    notes: str | None
    created_at: datetime
    warnings: list[Warning] = Field(default_factory=list)


class GraphEdge(BaseModel):
    id: uuid.UUID
    parent_id: uuid.UUID
    child_id: uuid.UUID
    type: ParentChildType


class GraphPartnership(BaseModel):
    id: uuid.UUID
    person_a_id: uuid.UUID
    person_b_id: uuid.UUID
    type: PartnershipType
    start_date: PartialDateOut | None
    end_date: PartialDateOut | None


class LayoutOffset(BaseModel):
    """Manual nudge of a card relative to the automatic layout (pixels)."""

    dx: float = Field(ge=-100_000, le=100_000)
    dy: float = Field(ge=-100_000, le=100_000)


class TreeGraph(BaseModel):
    persons: list[PersonSummary]
    parent_child: list[GraphEdge]
    partnerships: list[GraphPartnership]
    layout_offsets: dict[uuid.UUID, LayoutOffset] = Field(default_factory=dict)
