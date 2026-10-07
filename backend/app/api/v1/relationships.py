from __future__ import annotations

import uuid

from fastapi import APIRouter, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ActorDep, SessionDep, TreeEditor
from app.models import ParentChild, Partnership
from app.schemas.dates import PartialDateOut
from app.schemas.persons import Warning
from app.schemas.places import PlaceSummary
from app.schemas.relationships import (
    ParentChildCreate,
    ParentChildOut,
    ParentChildUpdate,
    PartnershipCreate,
    PartnershipOut,
    PartnershipUpdate,
)
from app.services.genealogy import relationships as rel_service
from app.services.genealogy.common import check_place

router = APIRouter(prefix="/trees/{tree_id}", tags=["relationships"])


def pc_out(link: ParentChild, warnings: list[Warning]) -> ParentChildOut:
    return ParentChildOut(
        id=link.id,
        parent_id=link.parent_id,
        child_id=link.child_id,
        type=link.type,
        notes=link.notes,
        created_at=link.created_at,
        warnings=warnings,
    )


async def partnership_out(session: AsyncSession, p: Partnership) -> PartnershipOut:
    place = await check_place(session, p.tree_id, p.place_id) if p.place_id else None
    return PartnershipOut(
        id=p.id,
        person_a_id=p.person_a_id,
        person_b_id=p.person_b_id,
        type=p.type,
        start_date=PartialDateOut.from_domain(p.start_date),
        end_date=PartialDateOut.from_domain(p.end_date),
        end_reason=p.end_reason,
        place=PlaceSummary.model_validate(place) if place else None,
        notes=p.notes,
        created_at=p.created_at,
    )


@router.post("/parent-child", response_model=ParentChildOut, status_code=status.HTTP_201_CREATED)
async def create_parent_child(
    body: ParentChildCreate, access: TreeEditor, session: SessionDep, actor: ActorDep
) -> ParentChildOut:
    """Link a parent and a child. Implausible dates are returned as `warnings`."""
    link, warnings = await rel_service.create_parent_child(session, access.tree.id, body, actor)
    return pc_out(link, warnings)


@router.patch("/parent-child/{link_id}", response_model=ParentChildOut)
async def update_parent_child(
    link_id: uuid.UUID,
    body: ParentChildUpdate,
    access: TreeEditor,
    session: SessionDep,
    actor: ActorDep,
) -> ParentChildOut:
    link = await rel_service.get_parent_child(session, access.tree.id, link_id)
    link, warnings = await rel_service.update_parent_child(session, link, body, actor)
    return pc_out(link, warnings)


@router.delete("/parent-child/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_parent_child(
    link_id: uuid.UUID, access: TreeEditor, session: SessionDep, actor: ActorDep
) -> None:
    link = await rel_service.get_parent_child(session, access.tree.id, link_id)
    await rel_service.delete_parent_child(session, link, actor)


@router.post("/partnerships", response_model=PartnershipOut, status_code=status.HTTP_201_CREATED)
async def create_partnership(
    body: PartnershipCreate, access: TreeEditor, session: SessionDep, actor: ActorDep
) -> PartnershipOut:
    p = await rel_service.create_partnership(session, access.tree.id, body, actor)
    return await partnership_out(session, p)


@router.patch("/partnerships/{partnership_id}", response_model=PartnershipOut)
async def update_partnership(
    partnership_id: uuid.UUID,
    body: PartnershipUpdate,
    access: TreeEditor,
    session: SessionDep,
    actor: ActorDep,
) -> PartnershipOut:
    p = await rel_service.get_partnership(session, access.tree.id, partnership_id)
    p = await rel_service.update_partnership(session, p, body, actor)
    return await partnership_out(session, p)


@router.delete("/partnerships/{partnership_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_partnership(
    partnership_id: uuid.UUID, access: TreeEditor, session: SessionDep, actor: ActorDep
) -> None:
    p = await rel_service.get_partnership(session, access.tree.id, partnership_id)
    await rel_service.delete_partnership(session, p, actor)
