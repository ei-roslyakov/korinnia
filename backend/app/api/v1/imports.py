"""GEDCOM import (phase 9): upload, preview, confirm, cancel, undo. Editors and admins."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile, status

from app.api.deps import ActorDep, SessionDep, TreeEditor
from app.core.enums import ImportStatus
from app.core.errors import AppError
from app.core.security import utcnow
from app.importers.gedcom.parser import looks_like_gedcom
from app.models import GedcomImport, User
from app.schemas.data_safety import GedcomConfirm, GedcomImportOut
from app.services import gedcom_import as service
from app.storage import Storage, get_storage

router = APIRouter(prefix="/trees/{tree_id}/imports", tags=["imports"])
StorageDep = Annotated[Storage, Depends(get_storage)]


async def _out(session: SessionDep, imp: GedcomImport) -> GedcomImportOut:
    user = await session.get(User, imp.created_by_id) if imp.created_by_id else None
    return GedcomImportOut(
        id=imp.id,
        status=imp.status,
        filename=imp.filename,
        size=imp.size,
        created_at=imp.created_at,
        finished_at=imp.finished_at,
        created_by=user.display_name if user else None,
        preview=imp.preview,
        result=imp.result,
        error=imp.error,
    )


async def _queue(session: SessionDep, imp: GedcomImport, step: str) -> None:
    from app.jobs.queue import enqueue_gedcom

    try:
        await enqueue_gedcom(step, imp.id)
    except Exception as exc:
        imp.status = ImportStatus.failed
        imp.error = "job_queue_unavailable"
        imp.finished_at = utcnow()
        await session.commit()
        raise AppError("job_queue_unavailable", status_code=503) from exc


@router.get("", response_model=list[GedcomImportOut])
async def list_imports(access: TreeEditor, session: SessionDep) -> list[GedcomImportOut]:
    return [await _out(session, i) for i in await service.list_imports(session, access.tree.id)]


@router.post("", response_model=GedcomImportOut, status_code=status.HTTP_202_ACCEPTED)
async def upload(
    access: TreeEditor,
    session: SessionDep,
    storage: StorageDep,
    actor: ActorDep,
    file: Annotated[UploadFile, File()],
) -> GedcomImportOut:
    """Upload a GEDCOM (.ged) file. It is analysed in the background; poll the import until
    its status is `ready` (or `failed`), then confirm it."""
    raw = await file.read(service.MAX_FILE_BYTES + 1)
    if len(raw) > service.MAX_FILE_BYTES:
        raise AppError("file_too_large", status_code=413)
    if not looks_like_gedcom(raw):
        raise AppError("not_gedcom", status_code=422)
    imp = await service.create_import(
        session, storage, access.tree, filename=file.filename or "family.ged", raw=raw, actor=actor
    )
    await _queue(session, imp, "analyze")
    return await _out(session, imp)


@router.get("/{import_id}", response_model=GedcomImportOut)
async def get_import(
    import_id: uuid.UUID, access: TreeEditor, session: SessionDep
) -> GedcomImportOut:
    return await _out(session, await service.get_import(session, access.tree.id, import_id))


@router.post("/{import_id}/confirm", response_model=GedcomImportOut)
async def confirm(
    import_id: uuid.UUID,
    body: GedcomConfirm,
    access: TreeEditor,
    session: SessionDep,
    actor: ActorDep,
) -> GedcomImportOut:
    """Start the import. `merge` maps people in the file to people already in the tree;
    everyone else is created."""
    imp = await service.get_import(session, access.tree.id, import_id)
    imp = await service.confirm(session, imp, body.merge, actor)
    await _queue(session, imp, "apply")
    return await _out(session, imp)


@router.post("/{import_id}/cancel", response_model=GedcomImportOut)
async def cancel(
    import_id: uuid.UUID, access: TreeEditor, session: SessionDep, actor: ActorDep
) -> GedcomImportOut:
    imp = await service.get_import(session, access.tree.id, import_id)
    return await _out(session, await service.cancel(session, imp, actor))


@router.post("/{import_id}/undo", response_model=GedcomImportOut)
async def undo(
    import_id: uuid.UUID, access: TreeEditor, session: SessionDep, actor: ActorDep
) -> GedcomImportOut:
    """Move everyone (and every source) the import created to the trash."""
    imp = await service.get_import(session, access.tree.id, import_id)
    imp = await service.start_undo(session, imp, actor)
    await _queue(session, imp, "undo")
    return await _out(session, imp)
