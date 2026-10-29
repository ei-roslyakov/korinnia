"""Media: upload, processing, tagging people, gallery order, primary photo and portrait."""

from __future__ import annotations

import hashlib
import io
import logging
import tempfile
import uuid
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO

from anyio import to_thread
from sqlalchemy import exists, extract, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError, ConflictError, NotFoundError
from app.core.security import utcnow
from app.media import processing
from app.media.detect import BROWSER_AUDIO, UnsupportedMediaError, detect, safe_filename
from app.models import (
    MediaFile,
    MediaKind,
    MediaPerson,
    Person,
    ProcessingStatus,
)
from app.schemas.dates import PartialDateOut
from app.schemas.media import (
    MediaOut,
    MediaPersonOut,
    MediaUpdate,
    MediaUrls,
    Region,
)
from app.schemas.places import PlaceSummary
from app.services import audit
from app.services.context import Actor
from app.services.genealogy.common import (
    check_persons,
    check_place,
    date_to_dict,
    get_live,
    set_date,
    to_partial,
)
from app.services.genealogy.media_urls import file_url
from app.services.genealogy.summaries import summary_map
from app.storage import Storage

logger = logging.getLogger(__name__)

COPY_CHUNK = 1024 * 1024
PHOTO_KINDS = (MediaKind.photo, MediaKind.document_scan)


# --- Output -----------------------------------------------------------------------------


async def media_out_many(session: AsyncSession, items: Sequence[MediaFile]) -> list[MediaOut]:
    if not items:
        return []
    tags = list(
        await session.scalars(
            select(MediaPerson).where(MediaPerson.media_id.in_([m.id for m in items]))
        )
    )
    tree_id = items[0].tree_id
    names = await summary_map(session, tree_id, {t.person_id for t in tags})
    places = {
        m.place_id: await check_place(session, m.tree_id, m.place_id) for m in items if m.place_id
    }
    out = []
    for m in items:
        place = places.get(m.place_id) if m.place_id else None
        out.append(
            MediaOut(
                id=m.id,
                kind=m.kind,
                title=m.title,
                description=m.description,
                date=PartialDateOut.from_domain(m.date),
                place=PlaceSummary.model_validate(place) if place else None,
                original_filename=m.original_filename,
                mime_type=m.mime_type,
                size=m.size,
                sha256=m.sha256,
                width=m.width,
                height=m.height,
                duration_seconds=m.duration_seconds,
                processing_status=m.processing_status,
                processing_error=m.processing_error,
                urls=MediaUrls(
                    original=file_url(m, "original"),
                    web=file_url(m, "web"),
                    thumb=file_url(m, "thumb") if m.thumb_key else None,
                ),
                people=[
                    MediaPersonOut(
                        person_id=t.person_id,
                        display_name=names[t.person_id].display_name,
                        region=Region.model_validate(t.region) if t.region else None,
                    )
                    for t in tags
                    if t.media_id == m.id and t.person_id in names
                ],
                created_at=m.created_at,
            )
        )
    return out


def snapshot(media: MediaFile, tags: Sequence[MediaPerson]) -> dict[str, Any]:
    return {
        "kind": media.kind.value,
        "title": media.title,
        "description": media.description,
        "date": date_to_dict(media.date),
        "place_id": str(media.place_id) if media.place_id else None,
        "original_filename": media.original_filename,
        "sha256": media.sha256,
        "people": sorted(
            ({"person_id": str(t.person_id), "region": t.region} for t in tags),
            key=lambda d: str(d["person_id"]),
        ),
    }


async def _tags(session: AsyncSession, media_id: uuid.UUID) -> list[MediaPerson]:
    return list(await session.scalars(select(MediaPerson).where(MediaPerson.media_id == media_id)))


# --- Upload -----------------------------------------------------------------------------


@dataclass
class Upload:
    file: BinaryIO
    filename: str
    size: int | None


def _spool_to_disk(src: BinaryIO, dest: Path, limit: int) -> tuple[str, int]:
    digest, size = hashlib.sha256(), 0
    with dest.open("wb") as out:
        while chunk := src.read(COPY_CHUNK):
            size += len(chunk)
            if size > limit:
                raise AppError("file_too_large", status_code=413)
            digest.update(chunk)
            out.write(chunk)
    return digest.hexdigest(), size


async def upload_media(
    session: AsyncSession,
    storage: Storage,
    tree_id: uuid.UUID,
    upload: Upload,
    *,
    actor: Actor,
    title: str | None = None,
    kind_hint: MediaKind | None = None,
    person_id: uuid.UUID | None = None,
    allow_duplicate: bool = False,
) -> MediaFile:
    settings = get_settings()
    limit = settings.max_upload_size_mb * 1024 * 1024
    if actor.user is not None and actor.user.is_sandbox:
        limit = min(limit, settings.demo_max_upload_mb * 1024 * 1024)
    if upload.size is not None and upload.size > limit:
        raise AppError("file_too_large", status_code=413)
    if person_id:
        await check_persons(session, tree_id, [person_id])

    with tempfile.TemporaryDirectory(prefix="korinnia-upload-") as tmp:
        path = Path(tmp) / "upload"
        sha, size = await to_thread.run_sync(_spool_to_disk, upload.file, path, limit)
        if size == 0:
            raise AppError("empty_file")
        try:
            detected = await to_thread.run_sync(detect, path, upload.filename)
        except UnsupportedMediaError as exc:
            raise AppError("unsupported_media_type", status_code=415) from exc

        existing = await session.scalar(
            select(MediaFile.id).where(
                MediaFile.tree_id == tree_id,
                MediaFile.sha256 == sha,
                MediaFile.deleted_at.is_(None),
            )
        )
        if existing and not allow_duplicate:
            raise ConflictError("duplicate_media", extra={"media_id": str(existing)})

        kind = detected.kind
        if kind_hint == MediaKind.document_scan and kind == MediaKind.photo:
            kind = MediaKind.document_scan
        media_id = uuid.uuid4()
        key = f"originals/{tree_id}/{media_id}/{safe_filename(upload.filename, detected.extension)}"
        with path.open("rb") as f:
            stored = await storage.put(key, f, content_type=detected.mime)

    user_id = actor.user.id if actor.user else None
    media = MediaFile(
        id=media_id,
        tree_id=tree_id,
        kind=kind,
        original_key=stored.key,
        original_filename=upload.filename[:500] or "file",
        mime_type=detected.mime,
        size=stored.size,
        sha256=stored.sha256,
        title=(title or "").strip() or None,
        processing_status=ProcessingStatus.pending,
        created_by_id=user_id,
        updated_by_id=user_id,
    )
    session.add(media)
    await session.flush()
    if person_id:
        await _link(session, media, person_id, None)
        person = await session.get(Person, person_id)
        if person and person.primary_photo_id is None and kind == MediaKind.photo:
            person.primary_photo_id = media.id  # first photo becomes the portrait
    audit.record(
        session, actor, "media.create", "media", media.id, tree_id=tree_id,
        after=snapshot(media, await _tags(session, media.id)),
    )  # fmt: skip
    await session.commit()
    return media


async def _link(
    session: AsyncSession, media: MediaFile, person_id: uuid.UUID, region: dict[str, Any] | None
) -> MediaPerson:
    tag = (
        await session.scalars(
            select(MediaPerson).where(
                MediaPerson.media_id == media.id, MediaPerson.person_id == person_id
            )
        )
    ).first()
    if tag is None:
        last = await session.scalar(
            select(func.max(MediaPerson.sort_order)).where(MediaPerson.person_id == person_id)
        )
        tag = MediaPerson(
            media_id=media.id, person_id=person_id, region=region, sort_order=(last or 0) + 1
        )
        session.add(tag)
    else:
        tag.region = region
    await session.flush()
    return tag


# --- Processing (worker) ----------------------------------------------------------------


async def process_media(session: AsyncSession, storage: Storage, media_id: uuid.UUID) -> None:
    """Generate derivatives for one item. Failures are recorded on the item, not raised."""
    media = await session.get(MediaFile, media_id)
    if media is None:
        return
    try:
        with tempfile.TemporaryDirectory(prefix="korinnia-media-") as tmp:
            workdir = Path(tmp)
            original = workdir / "original"
            with original.open("wb") as f:
                async for chunk in storage.open(media.original_key):
                    f.write(chunk)
            match media.kind:
                case MediaKind.photo | MediaKind.document_scan:
                    result = await to_thread.run_sync(processing.image_derivatives, original)
                case MediaKind.video:
                    result = await processing.video_derivatives(original, workdir)
                case MediaKind.audio:
                    result = await processing.audio_derivatives(
                        original, workdir, media.mime_type in BROWSER_AUDIO
                    )
                case MediaKind.pdf:
                    result = await processing.pdf_derivatives(original, workdir)
                case _:
                    result = processing.Derivatives()
        prefix = f"derived/{media.tree_id}/{media.id}"
        media.web_key = media.thumb_key = None
        for name, data in result.files.items():
            stored = await storage.put(f"{prefix}/{name}", io.BytesIO(data), overwrite=True)
            if name.startswith("web."):
                media.web_key = stored.key
            elif name.startswith("thumb."):
                media.thumb_key = stored.key
        media.width, media.height = result.width, result.height
        media.duration_seconds = result.duration
        media.processing_status = ProcessingStatus.ready
        media.processing_error = result.note
    except Exception as exc:
        logger.exception("media processing failed", extra={"media_id": str(media_id)})
        media.processing_status = ProcessingStatus.failed
        media.processing_error = f"{type(exc).__name__}: {exc}"[:2000]
    await session.commit()


async def make_avatar(session: AsyncSession, storage: Storage, person_id: uuid.UUID) -> None:
    """Render the person's portrait from the primary photo and crop (worker)."""
    person = await session.get(Person, person_id)
    if person is None or person.primary_photo_id is None:
        return
    media = await session.get(MediaFile, person.primary_photo_id)
    if media is None or media.deleted_at is not None or media.kind not in PHOTO_KINDS:
        return
    with tempfile.TemporaryDirectory(prefix="korinnia-avatar-") as tmp:
        original = Path(tmp) / "original"
        with original.open("wb") as f:
            async for chunk in storage.open(media.original_key):
                f.write(chunk)
        data = await to_thread.run_sync(processing.avatar, original, person.primary_photo_crop)
    version = hashlib.sha256(f"{media.sha256}{person.primary_photo_crop}".encode()).hexdigest()[:12]
    stored = await storage.put(
        f"avatars/{person.tree_id}/{person.id}/{version}.webp", io.BytesIO(data), overwrite=True
    )
    person.avatar_key = stored.key
    await session.commit()


# --- CRUD -------------------------------------------------------------------------------


async def get_media(session: AsyncSession, tree_id: uuid.UUID, media_id: uuid.UUID) -> MediaFile:
    return await get_live(session, MediaFile, tree_id, media_id, "media_not_found")


async def list_media(
    session: AsyncSession,
    tree_id: uuid.UUID,
    *,
    person_id: uuid.UUID | None,
    kind: MediaKind | None,
    q: str | None,
    limit: int,
    offset: int,
    hidden: Collection[uuid.UUID] = (),
) -> tuple[list[MediaFile], int]:
    """`hidden` media (of living people, for restricted readers) are left out."""
    stmt = select(MediaFile).where(
        MediaFile.tree_id == tree_id, MediaFile.deleted_at.is_(None), MediaFile.id.not_in(hidden)
    )
    if person_id:
        stmt = stmt.join(MediaPerson, MediaPerson.media_id == MediaFile.id).where(
            MediaPerson.person_id == person_id
        )
        order: Any = (MediaPerson.sort_order, MediaFile.created_at)
    else:
        order = (MediaFile.created_at.desc(), MediaFile.id)
    if kind:
        stmt = stmt.where(MediaFile.kind == kind)
    if q:
        stmt = stmt.where(_matches(q))
    total = await session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = await session.scalars(stmt.order_by(*order).limit(limit).offset(offset))
    return list(rows), total


def _matches(q: str) -> Any:
    """Title, description or file name contains `q` (case-insensitive)."""
    like = f"%{q.strip().lower()}%"
    return or_(
        func.lower(MediaFile.title).like(like),
        func.lower(MediaFile.description).like(like),
        func.lower(MediaFile.original_filename).like(like),
    )


async def list_album(
    session: AsyncSession,
    tree_id: uuid.UUID,
    *,
    person_ids: Sequence[uuid.UUID],
    year_from: int | None,
    year_to: int | None,
    q: str | None,
    newest: bool,
    limit: int,
    offset: int,
    hidden: Collection[uuid.UUID] = (),
) -> tuple[list[MediaFile], int, list[int]]:
    """The tree's photo album: processed, not deleted photos, by photo date (undated last)
    or newest upload first. Also returns the decades that have photos (for the filter;
    without the year range, so the choice never narrows itself)."""
    stmt = select(MediaFile).where(
        MediaFile.tree_id == tree_id,
        MediaFile.deleted_at.is_(None),
        MediaFile.kind == MediaKind.photo,
        MediaFile.processing_status == ProcessingStatus.ready,
        MediaFile.id.not_in(hidden),
    )
    if person_ids:
        stmt = stmt.where(
            exists().where(
                MediaPerson.media_id == MediaFile.id, MediaPerson.person_id.in_(person_ids)
            )
        )
    if q:
        stmt = stmt.where(_matches(q))
    year = extract("year", MediaFile.date_sort)
    dated = stmt.where(MediaFile.date_sort.is_not(None)).subquery()
    decades = sorted(
        int(d)
        for d in await session.scalars(
            select(func.floor(extract("year", dated.c.date_sort) / 10) * 10).distinct()
        )
    )
    if year_from is not None:
        stmt = stmt.where(year >= year_from)
    if year_to is not None:
        stmt = stmt.where(year <= year_to)
    if newest:
        order: Any = (MediaFile.created_at.desc(), MediaFile.id)
    else:
        order = (MediaFile.date_sort.asc().nulls_last(), MediaFile.created_at, MediaFile.id)
    total = await session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = await session.scalars(stmt.order_by(*order).limit(limit).offset(offset))
    return list(rows), total, decades


async def update_media(
    session: AsyncSession, media: MediaFile, body: MediaUpdate, actor: Actor
) -> MediaFile:
    tags = await _tags(session, media.id)
    before = snapshot(media, tags)
    fields = body.model_fields_set
    if body.kind is not None:
        is_image = media.mime_type.startswith("image/")
        if (body.kind in PHOTO_KINDS) != is_image:
            raise AppError("invalid_media_kind")
        media.kind = body.kind
    for f in ("title", "description"):
        if f in fields:
            setattr(media, f, getattr(body, f))
    if "date" in fields:
        set_date(media, "date", "date_sort", to_partial(body.date))
    if "place_id" in fields:
        await check_place(session, media.tree_id, body.place_id)
        media.place_id = body.place_id
    media.updated_by_id = actor.user.id if actor.user else None
    media.updated_at = utcnow()
    after = snapshot(media, tags)
    if before != after:
        audit.record(
            session, actor, "media.update", "media", media.id, tree_id=media.tree_id,
            before=before, after=after,
        )  # fmt: skip
    await session.commit()
    return media


async def delete_media(session: AsyncSession, media: MediaFile, actor: Actor) -> None:
    """Soft delete (trash). The original file stays on disk; restore brings it back."""
    media.deleted_at = utcnow()
    media.deleted_batch_id = media.id
    audit.record(
        session, actor, "media.delete", "media", media.id, tree_id=media.tree_id,
        before=snapshot(media, await _tags(session, media.id)),
    )  # fmt: skip
    await session.commit()


async def tag_person(
    session: AsyncSession,
    media: MediaFile,
    person_id: uuid.UUID,
    region: Region | None,
    actor: Actor,
) -> None:
    await check_persons(session, media.tree_id, [person_id])
    before = snapshot(media, await _tags(session, media.id))
    await _link(session, media, person_id, region.model_dump() if region else None)
    audit.record(
        session, actor, "media.tag", "media", media.id, tree_id=media.tree_id,
        before=before, after=snapshot(media, await _tags(session, media.id)),
    )  # fmt: skip
    await session.commit()


async def untag_person(
    session: AsyncSession, media: MediaFile, person_id: uuid.UUID, actor: Actor
) -> None:
    tags = await _tags(session, media.id)
    tag = next((t for t in tags if t.person_id == person_id), None)
    if tag is None:
        raise NotFoundError("tag_not_found")
    before = snapshot(media, tags)
    await session.delete(tag)
    person = await session.get(Person, person_id)
    if person and person.primary_photo_id == media.id:
        person.primary_photo_id = None
        person.primary_photo_crop = None
        person.avatar_key = None
    await session.flush()
    audit.record(
        session, actor, "media.untag", "media", media.id, tree_id=media.tree_id,
        before=before, after=snapshot(media, await _tags(session, media.id)),
    )  # fmt: skip
    await session.commit()


async def reorder_person_media(
    session: AsyncSession, person: Person, media_ids: list[uuid.UUID]
) -> None:
    tags = {
        t.media_id: t
        for t in await session.scalars(
            select(MediaPerson).where(MediaPerson.person_id == person.id)
        )
    }
    if set(media_ids) - set(tags):
        raise AppError("media_not_linked")
    for i, mid in enumerate(media_ids):
        tags[mid].sort_order = i
    await session.commit()


async def set_primary_photo(
    session: AsyncSession,
    person: Person,
    media_id: uuid.UUID | None,
    crop: Region | None,
) -> None:
    """Validate and apply a primary photo choice (caller commits and queues the portrait)."""
    if media_id is None:
        person.primary_photo_id = None
        person.primary_photo_crop = None
        person.avatar_key = None
        return
    media = await get_media(session, person.tree_id, media_id)
    if media.kind not in PHOTO_KINDS:
        raise AppError("not_a_photo")
    await _link(session, media, person.id, None)
    person.primary_photo_id = media.id
    person.primary_photo_crop = crop.model_dump() if crop else None
    person.avatar_key = None  # regenerated by the worker


def variant_key(media: MediaFile, variant: str) -> tuple[str, str] | None:
    """Storage key and content type for a requested variant."""
    if variant == "original":
        return media.original_key, media.mime_type
    if variant == "web":
        if media.web_key:
            ext = media.web_key.rsplit(".", 1)[-1]
            return media.web_key, {"webp": "image/webp", "mp4": "video/mp4", "mp3": "audio/mpeg"}[
                ext
            ]
        return media.original_key, media.mime_type
    if variant == "thumb" and media.thumb_key:
        return media.thumb_key, "image/webp"
    return None
