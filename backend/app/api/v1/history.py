"""Change history of genealogical entities (with restore) and the trash bin."""

from __future__ import annotations

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Query, status
from pydantic import BaseModel

from app.api.deps import ActorDep, PageParams, SessionDep, TreeEditor, TreeViewer
from app.jobs.queue import enqueue_avatar
from app.models import TreeRole
from app.schemas.audit import AuditEntryOut, AuditQuery
from app.schemas.common import Page
from app.schemas.history import TrashEntityType, TrashItem
from app.services import audit
from app.services.genealogy import trash as trash_service

router = APIRouter(prefix="/trees/{tree_id}", tags=["history"])

EntityType = Literal["person", "place", "event", "parent_child", "partnership", "media"]


class RestoredEntity(BaseModel):
    entity_type: str
    entity_id: uuid.UUID


@router.get("/history", response_model=Page[AuditEntryOut])
async def history(
    access: TreeViewer,
    session: SessionDep,
    page: PageParams,
    entity_type: EntityType,
    entity_id: Annotated[uuid.UUID | None, Query()] = None,
) -> Page[AuditEntryOut]:
    """Revisions of genealogical data with full before/after snapshots (newest first)."""
    q = AuditQuery(tree_id=access.tree.id, entity_type=entity_type, entity_id=entity_id)
    rows, total = await audit.list_entries(session, q, limit=page.limit, offset=page.offset)
    items = [AuditEntryOut.model_validate(r) for r in rows]
    if not access.role.at_least(TreeRole.admin):
        for item in items:
            item.ip_address = None
    return Page(items=items, total=total, limit=page.limit, offset=page.offset)


@router.post("/history/{entry_id}/restore", response_model=RestoredEntity)
async def restore_revision(
    entry_id: uuid.UUID, access: TreeEditor, session: SessionDep, actor: ActorDep
) -> RestoredEntity:
    """Restore the entity to its state right after the given change (recorded as a new
    revision, so the restore itself can be undone)."""
    entity_type, entity_id = await trash_service.restore_revision(
        session, access.tree.id, entry_id, actor
    )
    if entity_type == "person":
        await enqueue_avatar(entity_id)  # the restored photo choice needs a fresh portrait
    return RestoredEntity(entity_type=entity_type, entity_id=entity_id)


@router.get("/trash", response_model=list[TrashItem])
async def trash(access: TreeEditor, session: SessionDep) -> list[TrashItem]:
    return await trash_service.list_trash(session, access.tree.id)


@router.post("/trash/{entity_type}/{entity_id}/restore", status_code=status.HTTP_204_NO_CONTENT)
async def restore_from_trash(
    entity_type: TrashEntityType,
    entity_id: uuid.UUID,
    access: TreeEditor,
    session: SessionDep,
    actor: ActorDep,
) -> None:
    await trash_service.restore_from_trash(session, access.tree.id, entity_type, entity_id, actor)
