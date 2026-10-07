"""Read-only views over the whole tree: timeline, map, "on this day", kinship, statistics."""

from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

from app.core.enums import ParticipantRole
from app.schemas.dates import PartialDateOut
from app.schemas.persons import PersonSummary
from app.schemas.places import PlaceSummary

# --- Dated facts --------------------------------------------------------------------------

FactKind = Literal["event", "partnership_start", "partnership_end"]


class FactPerson(BaseModel):
    id: uuid.UUID
    display_name: str
    role: ParticipantRole


class Fact(BaseModel):
    """An event, or the start / end of a partnership, with its people and place.

    `type` is an event type (`birth`, `residence`, …) for events, and `marriage`,
    `partnership` or `divorce` / `separation` / `partnership_end` for partnerships.
    """

    kind: FactKind
    id: uuid.UUID  # event or partnership id
    type: str
    title: str | None
    date: PartialDateOut | None
    place: PlaceSummary | None
    # A precise spot (e.g. a grave) that overrides the place's coordinates.
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    cemetery_name: str | None = None
    persons: list[FactPerson]


class TimelinePage(BaseModel):
    items: list[Fact]
    total: int
    limit: int
    offset: int
    undated: int  # matching facts without a usable date (not listed)


class Anniversary(BaseModel):
    on: dt.date  # the calendar day in the requested window
    years: int  # how many years ago it happened (on `on`)
    fact: Fact


class OnThisDay(BaseModel):
    start: dt.date
    days: int
    items: list[Anniversary]


class MapPoint(BaseModel):
    latitude: Decimal
    longitude: Decimal
    label: str
    place_id: uuid.UUID | None
    facts: list[Fact]


class MapData(BaseModel):
    points: list[MapPoint]
    # Facts whose place has no coordinates yet (so they cannot be shown).
    unplaced: int
    places_without_coordinates: list[PlaceSummary]


# --- Kinship ------------------------------------------------------------------------------

Edge = Literal["parent", "child", "partner"]
KinshipKind = Literal["same", "blood", "partner", "in_law", "distant", "none"]


class PathStep(BaseModel):
    person: PersonSummary
    # How this person relates to the previous one in the path ("parent" = this person is
    # the previous person's parent). None for the first person.
    edge: Edge | None


class Relationship(BaseModel):
    """How `b` is related to `a`. The UI turns the structure into a kinship term.

    - blood: `up` generations from `a` to the closest common ancestor(s), then `down` to `b`.
    - partner: `b` is `a`'s partner.
    - in_law: `side` = "partner_relative" (`b` is a blood relative of `a`'s partner `via`;
      `up`/`down` measured from `via`) or "relative_partner" (`b` is the partner of `a`'s
      blood relative `via`; `up`/`down` measured from `a` to `via`).
    - distant: connected only through a longer chain; see `path`.
    """

    a: PersonSummary
    b: PersonSummary
    kind: KinshipKind
    up: int | None = None
    down: int | None = None
    half: bool = False
    # The blood line runs through an adoptive / step / foster / unknown link.
    non_biological: bool = False
    side: Literal["partner_relative", "relative_partner"] | None = None
    via: PersonSummary | None = None
    common_ancestors: list[PersonSummary] = []
    path: list[PathStep] = []


# --- Statistics ---------------------------------------------------------------------------


class NameCount(BaseModel):
    name: str  # the most common spelling
    count: int  # people bearing it (each person counted once)
    variants: list[str] = []  # other spellings / scripts grouped with it


class DecadeCount(BaseModel):
    decade: int
    births: int
    deaths: int


class PersonFigure(BaseModel):
    person: PersonSummary
    years: int | None = None


class TreeStats(BaseModel):
    persons: int
    male: int
    female: int
    other_gender: int
    living: int
    deceased: int
    generations: int
    partnerships: int
    places: int
    events: int
    media: int
    sources: int
    stories: int
    earliest_year: int | None
    latest_year: int | None
    oldest_ancestor: PersonFigure | None
    longest_lived: PersonFigure | None
    average_lifespan: float | None
    lifespan_sample: int
    surnames: list[NameCount]
    first_names: list[NameCount]
    by_decade: list[DecadeCount]
