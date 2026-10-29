"""One person's ancestors or descendants as a compact graph, for the chart views (D118)."""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel

from app.core.enums import ParentChildType, PartnershipType
from app.schemas.persons import PersonSummary

Direction = Literal["ancestors", "descendants"]
MAX_ANCESTOR_DEPTH = 10
MAX_DESCENDANT_DEPTH = 8


class LineageLink(BaseModel):
    parent_id: uuid.UUID
    child_id: uuid.UUID
    type: ParentChildType


class LineagePartnership(BaseModel):
    id: uuid.UUID
    person_a_id: uuid.UUID
    person_b_id: uuid.UUID
    type: PartnershipType
    year: int | None  # when it began


class Lineage(BaseModel):
    root_id: uuid.UUID
    direction: Direction
    depth: int  # generations asked for (the root is generation 0)
    persons: list[PersonSummary]
    parent_links: list[LineageLink]
    # Descendants only: the partners of everyone in the chart, with their partnerships.
    partnerships: list[LineagePartnership]
    # Ancestors reached through more than one line (pedigree collapse): drawn again, marked.
    repeated: list[uuid.UUID]
    # More generations exist beyond `depth`.
    truncated: bool
