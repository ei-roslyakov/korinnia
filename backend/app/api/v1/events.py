from __future__ import annotations

import uuid

from fastapi import APIRouter, status

from app.api.deps import ActorDep, SessionDep, TreeEditor, TreeViewer, VisibilityDep
from app.core.errors import NotFoundError
from app.schemas.events import EventCreate, EventOut, EventUpdate
from app.services.genealogy import events as event_service
from app.services.genealogy.persons import events_out

router = APIRouter(prefix="/trees/{tree_id}/events", tags=["events"])


@router.post("", response_model=EventOut, status_code=status.HTTP_201_CREATED)
async def create_event(
    body: EventCreate, access: TreeEditor, session: SessionDep, actor: ActorDep
) -> EventOut:
    event = await event_service.create_event(session, access.tree.id, body, actor)
    return (await events_out(session, access.tree.id, [event]))[0]


@router.get("/{event_id}", response_model=EventOut)
async def get_event(
    event_id: uuid.UUID, access: TreeViewer, session: SessionDep, seen: VisibilityDep
) -> EventOut:
    if seen.hides_event(event_id):
        raise NotFoundError("event_not_found")
    event = await event_service.get_event(session, access.tree.id, event_id)
    return (await events_out(session, access.tree.id, [event]))[0]


@router.patch("/{event_id}", response_model=EventOut)
async def update_event(
    event_id: uuid.UUID, body: EventUpdate, access: TreeEditor, session: SessionDep, actor: ActorDep
) -> EventOut:
    event = await event_service.get_event(session, access.tree.id, event_id)
    event = await event_service.update_event(session, event, body, actor)
    return (await events_out(session, access.tree.id, [event]))[0]


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(
    event_id: uuid.UUID, access: TreeEditor, session: SessionDep, actor: ActorDep
) -> None:
    event = await event_service.get_event(session, access.tree.id, event_id)
    await event_service.delete_event(session, event, actor)
