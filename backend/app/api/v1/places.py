from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import ActorDep, PageParams, SessionDep, TreeEditor, TreeViewer
from app.schemas.common import Page
from app.schemas.places import PlaceCreate, PlaceOut, PlaceUpdate
from app.services.genealogy import places as place_service

router = APIRouter(prefix="/trees/{tree_id}/places", tags=["places"])


@router.get("", response_model=Page[PlaceOut])
async def list_places(
    access: TreeViewer,
    session: SessionDep,
    page: PageParams,
    q: Annotated[str | None, Query(max_length=200)] = None,
) -> Page[PlaceOut]:
    """List places; `q` matches current and historical names in any script (autocomplete)."""
    rows, total = await place_service.search_places(
        session, access.tree.id, q, limit=page.limit, offset=page.offset
    )
    return Page(
        items=[PlaceOut.model_validate(p) for p in rows],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.post("", response_model=PlaceOut, status_code=status.HTTP_201_CREATED)
async def create_place(
    body: PlaceCreate, access: TreeEditor, session: SessionDep, actor: ActorDep
) -> PlaceOut:
    place = await place_service.create_place(session, access.tree.id, body, actor)
    return PlaceOut.model_validate(place)


@router.get("/{place_id}", response_model=PlaceOut)
async def get_place(place_id: uuid.UUID, access: TreeViewer, session: SessionDep) -> PlaceOut:
    return PlaceOut.model_validate(await place_service.get_place(session, access.tree.id, place_id))


@router.patch("/{place_id}", response_model=PlaceOut)
async def update_place(
    place_id: uuid.UUID, body: PlaceUpdate, access: TreeEditor, session: SessionDep, actor: ActorDep
) -> PlaceOut:
    place = await place_service.get_place(session, access.tree.id, place_id)
    return PlaceOut.model_validate(await place_service.update_place(session, place, body, actor))


@router.delete("/{place_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_place(
    place_id: uuid.UUID, access: TreeEditor, session: SessionDep, actor: ActorDep
) -> None:
    place = await place_service.get_place(session, access.tree.id, place_id)
    await place_service.delete_place(session, place, actor)
