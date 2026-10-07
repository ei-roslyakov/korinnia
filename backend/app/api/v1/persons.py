from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import ActorDep, PageParams, SessionDep, TreeEditor, TreeViewer
from app.schemas.common import Page
from app.schemas.persons import (
    DeletePreview,
    PersonCreate,
    PersonDetail,
    PersonSummary,
    PersonUpdate,
)
from app.schemas.relationships import TreeGraph
from app.services.genealogy import persons as person_service
from app.services.genealogy import trash as trash_service
from app.services.genealogy.graph import tree_graph

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


@router.post("/persons", response_model=PersonDetail, status_code=status.HTTP_201_CREATED)
async def create_person(
    body: PersonCreate, access: TreeEditor, session: SessionDep, actor: ActorDep
) -> PersonDetail:
    person = await person_service.create_person(session, access.tree.id, body, actor)
    return await person_service.person_detail(session, person)


@router.get("/persons/{person_id}", response_model=PersonDetail)
async def get_person(person_id: uuid.UUID, access: TreeViewer, session: SessionDep) -> PersonDetail:
    person = await person_service.get_person(session, access.tree.id, person_id)
    return await person_service.person_detail(session, person)


@router.patch("/persons/{person_id}", response_model=PersonDetail)
async def update_person(
    person_id: uuid.UUID,
    body: PersonUpdate,
    access: TreeEditor,
    session: SessionDep,
    actor: ActorDep,
) -> PersonDetail:
    person = await person_service.get_person(session, access.tree.id, person_id)
    person = await person_service.update_person(session, person, body, actor)
    return await person_service.person_detail(session, person)


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
