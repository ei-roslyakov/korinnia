from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import ActorDep, PageParams, SessionDep, TreeEditor, TreeViewer
from app.jobs.queue import enqueue_avatar
from app.schemas.common import Page
from app.schemas.person_page import PersonPage
from app.schemas.persons import (
    DeletePreview,
    PersonCreate,
    PersonSummary,
    PersonUpdate,
)
from app.schemas.relationships import LayoutOffset, LayoutOffsets, TreeGraph
from app.services.genealogy import builder as builder_service
from app.services.genealogy import persons as person_service
from app.services.genealogy import trash as trash_service
from app.services.genealogy.graph import tree_graph
from app.services.genealogy.person_page import person_page

router = APIRouter(prefix="/trees/{tree_id}", tags=["persons"])


@router.get("/graph", response_model=TreeGraph)
async def graph(access: TreeViewer, session: SessionDep) -> TreeGraph:
    """All people and relationships of the tree, for the canvas."""
    return await tree_graph(session, access.tree.id)


@router.get("/persons", response_model=Page[PersonSummary])
async def list_persons(
    access: TreeViewer,
    session: SessionDep,
    page: PageParams,
    q: Annotated[str | None, Query(max_length=200)] = None,
) -> Page[PersonSummary]:
    """Search by any name variant (Cyrillic or Latin) and/or a birth/death year."""
    items, total = await person_service.search_persons(
        session, access.tree.id, q, limit=page.limit, offset=page.offset
    )
    return Page(items=items, total=total, limit=page.limit, offset=page.offset)


@router.post("/persons", response_model=PersonPage, status_code=status.HTTP_201_CREATED)
async def create_person(
    body: PersonCreate, access: TreeEditor, session: SessionDep, actor: ActorDep
) -> PersonPage:
    """Create a person; with `relative` also link them to an existing person atomically."""
    person = await builder_service.create_person_with_relative(session, access.tree.id, body, actor)
    return await person_page(session, person, access.user, access.role)


@router.get("/persons/{person_id}", response_model=PersonPage)
async def get_person(person_id: uuid.UUID, access: TreeViewer, session: SessionDep) -> PersonPage:
    person = await person_service.get_person(session, access.tree.id, person_id)
    return await person_page(session, person, access.user, access.role)


@router.patch("/persons/{person_id}", response_model=PersonPage)
async def update_person(
    person_id: uuid.UUID,
    body: PersonUpdate,
    access: TreeEditor,
    session: SessionDep,
    actor: ActorDep,
) -> PersonPage:
    person = await person_service.get_person(session, access.tree.id, person_id)
    person = await person_service.update_person(session, person, body, actor)
    if {
        "primary_photo_id",
        "primary_photo_crop",
    } & body.model_fields_set and person.primary_photo_id:
        await enqueue_avatar(person.id)
    return await person_page(session, person, access.user, access.role)


@router.get("/persons/{person_id}/delete-preview", response_model=DeletePreview)
async def delete_preview(
    person_id: uuid.UUID, access: TreeEditor, session: SessionDep
) -> DeletePreview:
    """What else is moved to the trash together with this person."""
    person = await person_service.get_person(session, access.tree.id, person_id)
    return await trash_service.delete_preview(session, person)


@router.delete("/persons/{person_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_person(
    person_id: uuid.UUID, access: TreeEditor, session: SessionDep, actor: ActorDep
) -> None:
    person = await person_service.get_person(session, access.tree.id, person_id)
    await trash_service.delete_person(session, person, actor)


@router.put("/layout-offsets/{person_id}", status_code=status.HTTP_204_NO_CONTENT)
async def set_layout_offset(
    person_id: uuid.UUID, body: LayoutOffset, access: TreeEditor, session: SessionDep
) -> None:
    """Save a manual nudge of a card on the canvas (0,0 removes it). Not audited:
    presentation only, not family data."""
    await builder_service.set_layout_offset(session, access.tree.id, person_id, body)


@router.put("/layout-offsets", status_code=status.HTTP_204_NO_CONTENT)
async def set_layout_offsets(body: LayoutOffsets, access: TreeEditor, session: SessionDep) -> None:
    """Save the positions of several cards at once (dragging a whole branch)."""
    await builder_service.set_layout_offsets(session, access.tree.id, body.offsets)


@router.delete("/layout-offsets", status_code=status.HTTP_204_NO_CONTENT)
async def reset_layout(access: TreeEditor, session: SessionDep) -> None:
    """Forget all manual card positions of the tree."""
    await builder_service.reset_layout(session, access.tree.id)
