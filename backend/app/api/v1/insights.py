"""Read-only views over the whole tree: timeline, map, on this day, kinship, statistics."""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import SessionDep, TreeViewer
from app.schemas.insights import MapData, OnThisDay, Relationship, TimelinePage, TreeStats
from app.services.genealogy import facts as facts_service
from app.services.genealogy.kinship import relationship
from app.services.genealogy.persons import get_person
from app.services.genealogy.stats import tree_stats

router = APIRouter(prefix="/trees/{tree_id}", tags=["insights"])


@router.get("/timeline", response_model=TimelinePage)
async def timeline(
    access: TreeViewer,
    session: SessionDep,
    type: Annotated[list[str] | None, Query(max_length=40)] = None,
    person_id: uuid.UUID | None = None,
    from_year: Annotated[int | None, Query(ge=1, le=9999)] = None,
    to_year: Annotated[int | None, Query(ge=1, le=9999)] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> TimelinePage:
    """All dated events and marriages of the family in chronological order."""
    return await facts_service.timeline(
        session,
        access.tree.id,
        types=type,
        person_id=person_id,
        from_year=from_year,
        to_year=to_year,
        limit=limit,
        offset=offset,
    )


@router.get("/on-this-day", response_model=OnThisDay)
async def on_this_day(
    access: TreeViewer,
    session: SessionDep,
    date: dt.date | None = None,
    days: Annotated[int, Query(ge=0, le=facts_service.MAX_WINDOW_DAYS)] = 0,
) -> OnThisDay:
    """Birthdays, wedding anniversaries and memorial days on `date` (default: today) and
    the following `days` days. Only exactly dated facts are included."""
    return await facts_service.on_this_day(session, access.tree.id, date or dt.date.today(), days)


@router.get("/map", response_model=MapData)
async def map_data(
    access: TreeViewer, session: SessionDep, person_id: uuid.UUID | None = None
) -> MapData:
    """Facts grouped by location (place coordinates, or a precise spot such as a grave)."""
    return await facts_service.map_data(session, access.tree.id, person_id)


@router.get("/relationship", response_model=Relationship)
async def kinship(
    access: TreeViewer, session: SessionDep, a: uuid.UUID, b: uuid.UUID
) -> Relationship:
    """How person `b` is related to person `a`."""
    for pid in (a, b):
        await get_person(session, access.tree.id, pid)
    return await relationship(session, access.tree.id, a, b)


@router.get("/stats", response_model=TreeStats)
async def stats(access: TreeViewer, session: SessionDep) -> TreeStats:
    return await tree_stats(session, access.tree.id)
