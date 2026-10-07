"""Media: upload, list, edit, tag people, serve files (via nginx X-Accel-Redirect)."""

from __future__ import annotations

import uuid
from typing import Annotated, Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Query, Request, Response, UploadFile, status
from fastapi.responses import FileResponse

from app.api.deps import ActorDep, PageParams, SessionDep, TreeEditor, TreeViewer
from app.core.config import get_settings
from app.core.errors import NotFoundError
from app.jobs.queue import enqueue_avatar, enqueue_media_processing
from app.models import MediaFile, MediaKind, Person
from app.schemas.common import Page
from app.schemas.media import MediaOrder, MediaOut, MediaUpdate, TagIn, TagUpdate
from app.services.genealogy import media as media_service
from app.services.genealogy.common import get_live
from app.storage import LocalStorage, Storage, get_storage

router = APIRouter(prefix="/trees/{tree_id}", tags=["media"])

StorageDep = Annotated[Storage, Depends(get_storage)]
Variant = Literal["original", "web", "thumb"]


async def _out(session: SessionDep, media: MediaFile) -> MediaOut:
    return (await media_service.media_out_many(session, [media]))[0]


@router.post("/media", response_model=MediaOut, status_code=status.HTTP_201_CREATED)
async def upload(
    access: TreeEditor,
    session: SessionDep,
    storage: StorageDep,
    actor: ActorDep,
    file: Annotated[UploadFile, File()],
    title: Annotated[str | None, Form(max_length=300)] = None,
    kind: Annotated[Literal["photo", "document_scan"] | None, Form()] = None,
    person_id: Annotated[uuid.UUID | None, Form()] = None,
    allow_duplicate: Annotated[bool, Form()] = False,
) -> MediaOut:
    """Upload a photo, document scan, PDF, audio or video. The original is stored as is;
    previews are generated in the background (`processing_status`). The file type is
    detected from its content; the same file cannot be uploaded twice to a tree unless
    `allow_duplicate` is set (409 `duplicate_media` with the existing `media_id`)."""
    media = await media_service.upload_media(
        session,
        storage,
        access.tree.id,
        media_service.Upload(file=file.file, filename=file.filename or "file", size=file.size),
        actor=actor,
        title=title,
        kind_hint=MediaKind(kind) if kind else None,
        person_id=person_id,
        allow_duplicate=allow_duplicate,
    )
    await enqueue_media_processing(media.id)
    if person_id:
        person = await session.get(Person, person_id)
        if person and person.primary_photo_id == media.id:
            await enqueue_avatar(person.id)
    return await _out(session, media)


@router.get("/media", response_model=Page[MediaOut])
async def list_media(
    access: TreeViewer,
    session: SessionDep,
    page: PageParams,
    person_id: uuid.UUID | None = None,
    kind: MediaKind | None = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
) -> Page[MediaOut]:
    items, total = await media_service.list_media(
        session, access.tree.id, person_id=person_id, kind=kind, q=q,
        limit=page.limit, offset=page.offset,
    )  # fmt: skip
    return Page(
        items=await media_service.media_out_many(session, items),
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get("/media/{media_id}", response_model=MediaOut)
async def get_media(media_id: uuid.UUID, access: TreeViewer, session: SessionDep) -> MediaOut:
    return await _out(session, await media_service.get_media(session, access.tree.id, media_id))


@router.patch("/media/{media_id}", response_model=MediaOut)
async def update_media(
    media_id: uuid.UUID, body: MediaUpdate, access: TreeEditor, session: SessionDep, actor: ActorDep
) -> MediaOut:
    media = await media_service.get_media(session, access.tree.id, media_id)
    return await _out(session, await media_service.update_media(session, media, body, actor))


@router.delete("/media/{media_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_media(
    media_id: uuid.UUID, access: TreeEditor, session: SessionDep, actor: ActorDep
) -> None:
    media = await media_service.get_media(session, access.tree.id, media_id)
    await media_service.delete_media(session, media, actor)


@router.post("/media/{media_id}/reprocess", response_model=MediaOut)
async def reprocess(media_id: uuid.UUID, access: TreeEditor, session: SessionDep) -> MediaOut:
    """Regenerate previews (e.g. after a failure or a processing upgrade)."""
    media = await media_service.get_media(session, access.tree.id, media_id)
    await enqueue_media_processing(media.id)
    return await _out(session, media)


@router.post("/media/{media_id}/people", response_model=MediaOut)
async def tag_person(
    media_id: uuid.UUID, body: TagIn, access: TreeEditor, session: SessionDep, actor: ActorDep
) -> MediaOut:
    """Link a person to the item, optionally marking their face (region)."""
    media = await media_service.get_media(session, access.tree.id, media_id)
    await media_service.tag_person(session, media, body.person_id, body.region, actor)
    return await _out(session, media)


@router.patch("/media/{media_id}/people/{person_id}", response_model=MediaOut)
async def update_tag(
    media_id: uuid.UUID,
    person_id: uuid.UUID,
    body: TagUpdate,
    access: TreeEditor,
    session: SessionDep,
    actor: ActorDep,
) -> MediaOut:
    media = await media_service.get_media(session, access.tree.id, media_id)
    await media_service.tag_person(session, media, person_id, body.region, actor)
    return await _out(session, media)


@router.delete("/media/{media_id}/people/{person_id}", response_model=MediaOut)
async def untag_person(
    media_id: uuid.UUID,
    person_id: uuid.UUID,
    access: TreeEditor,
    session: SessionDep,
    actor: ActorDep,
) -> MediaOut:
    media = await media_service.get_media(session, access.tree.id, media_id)
    await media_service.untag_person(session, media, person_id, actor)
    return await _out(session, media)


@router.put("/persons/{person_id}/media-order", status_code=status.HTTP_204_NO_CONTENT)
async def reorder(
    person_id: uuid.UUID, body: MediaOrder, access: TreeEditor, session: SessionDep
) -> None:
    """Set the order of a person's gallery (ids of linked media, first = first)."""
    person = await get_live(session, Person, access.tree.id, person_id, "person_not_found")
    await media_service.reorder_person_media(session, person, body.media_ids)


# --- Files ------------------------------------------------------------------------------


# nginx sets this on every request it proxies to the API; only then can it act on
# X-Accel-Redirect. Requests reaching the backend another way (the Vite dev server,
# port 8000, tests) get the file itself.
VIA_NGINX_HEADER = "x-media-accel"


def _file_response(
    request: Request, storage: Storage, key: str, content_type: str, filename: str
) -> Response:
    disposition = f"inline; filename*=UTF-8''{quote(filename)}"
    headers = {
        "Content-Disposition": disposition,
        "Cache-Control": "private, max-age=3600",
        "X-Content-Type-Options": "nosniff",
    }
    if get_settings().media_x_accel and request.headers.get(VIA_NGINX_HEADER) == "1":
        # nginx streams the file itself (range requests, no Python in the data path).
        headers["X-Accel-Redirect"] = "/_media/" + quote(key)
        return Response(status_code=200, media_type=content_type, headers=headers)
    if not isinstance(storage, LocalStorage):  # pragma: no cover - only backend today
        raise NotFoundError("file_not_found")
    return FileResponse(storage.path(key), media_type=content_type, headers=headers)


@router.get("/media/{media_id}/file/{variant}")
async def media_file(
    request: Request,
    media_id: uuid.UUID,
    variant: Variant,
    access: TreeViewer,
    session: SessionDep,
    storage: StorageDep,
) -> Response:
    """The original or a derived version. Requires read access to the tree."""
    media = await media_service.get_media(session, access.tree.id, media_id)
    found = media_service.variant_key(media, variant)
    if found is None:
        raise NotFoundError("file_not_found")
    key, content_type = found
    name = media.original_filename
    if variant != "original":
        name = f"{name.rsplit('.', 1)[0]}-{variant}.{key.rsplit('.', 1)[-1]}"
    return _file_response(request, storage, key, content_type, name)


@router.get("/persons/{person_id}/avatar")
async def person_avatar(
    request: Request,
    person_id: uuid.UUID,
    access: TreeViewer,
    session: SessionDep,
    storage: StorageDep,
) -> Response:
    person = await get_live(session, Person, access.tree.id, person_id, "person_not_found")
    if not person.avatar_key:
        raise NotFoundError("file_not_found")
    return _file_response(
        request, storage, person.avatar_key, "image/webp", f"portrait-{person_id}.webp"
    )
