"""URLs of media files and portraits (no dependencies on other genealogy services)."""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MediaFile, Person


def file_url(media: MediaFile, variant: str) -> str:
    # The sha prefix busts browser caches if an item is ever re-processed / replaced.
    return f"/api/v1/trees/{media.tree_id}/media/{media.id}/file/{variant}?v={media.sha256[:8]}"


def avatar_url(person: Person, primary: MediaFile | None) -> str | None:
    if person.avatar_key:
        version = hashlib.sha256(person.avatar_key.encode()).hexdigest()[:8]
        return f"/api/v1/trees/{person.tree_id}/persons/{person.id}/avatar?v={version}"
    if primary is not None and primary.deleted_at is None and primary.thumb_key:
        return file_url(primary, "thumb")
    return None


async def primary_media_map(
    session: AsyncSession, persons: Sequence[Person]
) -> dict[uuid.UUID, MediaFile]:
    ids = {p.primary_photo_id for p in persons if p.primary_photo_id}
    if not ids:
        return {}
    rows = await session.scalars(select(MediaFile).where(MediaFile.id.in_(ids)))
    return {m.id: m for m in rows}
