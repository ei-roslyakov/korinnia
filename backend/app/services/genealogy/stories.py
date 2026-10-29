"""Stories and memories, with moderation for contributors.

Lifecycle: draft → pending_review (contributor submits) → published (editor publishes).
An editor can return a submitted story to draft with a comment. Viewers see only
published stories; authors also see their own drafts; editors see everything.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Collection, Sequence
from typing import Any

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, NotFoundError, PermissionDeniedError
from app.core.security import utcnow
from app.models import (
    MediaFile,
    MediaKind,
    Person,
    Story,
    StoryMedia,
    StoryPerson,
    StoryStatus,
    TreeRole,
    User,
)
from app.schemas.dates import PartialDateOut
from app.schemas.stories import StoryCreate, StoryOut, StorySummary, StoryUpdate
from app.services import audit
from app.services.context import Actor
from app.services.genealogy.common import (
    check_persons,
    date_from_dict,
    date_to_dict,
    get_live,
    set_date,
    to_partial,
)
from app.services.genealogy.media import media_out_many
from app.services.genealogy.media_urls import file_url
from app.services.genealogy.sources import user_refs
from app.services.genealogy.summaries import summary_map
from app.services.visibility import EVERYTHING, Visibility

EXCERPT_LENGTH = 240


def is_editor(role: TreeRole) -> bool:
    return role.at_least(TreeRole.editor)


def excerpt(markdown: str) -> str:
    text = re.sub(r"[#*_>`\[\]()!-]+", " ", markdown)
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= EXCERPT_LENGTH else text[: EXCERPT_LENGTH - 1].rstrip() + "…"


def can_view(story: Story, user: User, role: TreeRole) -> bool:
    return (
        story.status == StoryStatus.published or is_editor(role) or story.author_user_id == user.id
    )


def can_edit(story: Story, user: User, role: TreeRole) -> bool:
    if is_editor(role):
        return True
    return (
        role.at_least(TreeRole.contributor)
        and story.author_user_id == user.id
        and story.status != StoryStatus.published
    )


async def _links(
    session: AsyncSession, story_ids: Sequence[uuid.UUID]
) -> tuple[dict[uuid.UUID, list[uuid.UUID]], dict[uuid.UUID, list[uuid.UUID]]]:
    persons: dict[uuid.UUID, list[uuid.UUID]] = {sid: [] for sid in story_ids}
    media: dict[uuid.UUID, list[uuid.UUID]] = {sid: [] for sid in story_ids}
    for sid, pid in (
        await session.execute(
            select(StoryPerson.story_id, StoryPerson.person_id)
            .join(Person, Person.id == StoryPerson.person_id)
            .where(StoryPerson.story_id.in_(story_ids), Person.deleted_at.is_(None))
        )
    ).all():
        persons[sid].append(pid)
    for sid, mid in (
        await session.execute(
            select(StoryMedia.story_id, StoryMedia.media_id)
            .join(MediaFile, MediaFile.id == StoryMedia.media_id)
            .where(StoryMedia.story_id.in_(story_ids), MediaFile.deleted_at.is_(None))
        )
    ).all():
        media[sid].append(mid)
    return persons, media


def snapshot(
    story: Story, person_ids: Sequence[uuid.UUID], media_ids: Sequence[uuid.UUID]
) -> dict[str, Any]:
    return {
        "title": story.title,
        "body": story.body,
        "narrator": story.narrator,
        "date": date_to_dict(story.date),
        "status": story.status.value,
        "person_ids": sorted(str(p) for p in person_ids),
        "media_ids": sorted(str(m) for m in media_ids),
    }


async def snapshot_of(session: AsyncSession, story: Story) -> dict[str, Any]:
    persons, media = await _links(session, [story.id])
    return snapshot(story, persons[story.id], media[story.id])


async def apply_snapshot(session: AsyncSession, story: Story, snap: dict[str, Any]) -> None:
    story.title = snap["title"]
    story.body = snap.get("body") or ""
    story.narrator = snap.get("narrator")
    set_date(story, "date", "date_sort", date_from_dict(snap.get("date")))
    story.status = StoryStatus(snap["status"])
    await _set_links(
        session,
        story,
        [uuid.UUID(p) for p in snap.get("person_ids", [])],
        [uuid.UUID(m) for m in snap.get("media_ids", [])],
        validate=False,
    )


async def _set_links(
    session: AsyncSession,
    story: Story,
    person_ids: list[uuid.UUID] | None,
    media_ids: list[uuid.UUID] | None,
    *,
    validate: bool = True,
) -> None:
    if person_ids is not None:
        if validate:
            await check_persons(session, story.tree_id, person_ids)
        await session.execute(delete(StoryPerson).where(StoryPerson.story_id == story.id))
        session.add_all(
            StoryPerson(story_id=story.id, person_id=p) for p in dict.fromkeys(person_ids)
        )
    if media_ids is not None:
        if validate:
            for mid in media_ids:
                await get_live(session, MediaFile, story.tree_id, mid, "media_not_found")
        await session.execute(delete(StoryMedia).where(StoryMedia.story_id == story.id))
        session.add_all(StoryMedia(story_id=story.id, media_id=m) for m in dict.fromkeys(media_ids))
    await session.flush()


# --- Reading ----------------------------------------------------------------------------


async def get_story(
    session: AsyncSession, tree_id: uuid.UUID, story_id: uuid.UUID, user: User, role: TreeRole
) -> Story:
    story = await get_live(session, Story, tree_id, story_id, "story_not_found")
    if not can_view(story, user, role):
        raise NotFoundError("story_not_found")
    return story


def _visible(stmt: Any, user: User, role: TreeRole) -> Any:
    if is_editor(role):
        return stmt
    return stmt.where(or_(Story.status == StoryStatus.published, Story.author_user_id == user.id))


async def list_stories(
    session: AsyncSession,
    tree_id: uuid.UUID,
    user: User,
    role: TreeRole,
    *,
    person_id: uuid.UUID | None = None,
    status: StoryStatus | None = None,
    limit: int = 50,
    offset: int = 0,
    hidden: Collection[uuid.UUID] = (),
) -> tuple[list[Story], int]:
    """Stories this user may read. With `hidden` people (living, for readers who see only
    their basics), stories about nobody else are left out."""
    stmt = _visible(
        select(Story).where(Story.tree_id == tree_id, Story.deleted_at.is_(None)), user, role
    )
    if hidden:
        about_others = (
            select(StoryPerson.story_id)
            .join(Person, Person.id == StoryPerson.person_id)
            .where(StoryPerson.person_id.not_in(hidden), Person.deleted_at.is_(None))
        )
        about_anyone = (
            select(StoryPerson.story_id)
            .join(Person, Person.id == StoryPerson.person_id)
            .where(Person.deleted_at.is_(None))
        )
        stmt = stmt.where(or_(Story.id.in_(about_others), Story.id.not_in(about_anyone)))
    if person_id:
        stmt = stmt.where(
            Story.id.in_(select(StoryPerson.story_id).where(StoryPerson.person_id == person_id))
        )
    if status:
        stmt = stmt.where(Story.status == status)
    total = await session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = await session.scalars(
        stmt.order_by(Story.date_sort.asc().nulls_last(), Story.created_at)
        .limit(limit)
        .offset(offset)
    )
    return list(rows), total


WORDS_PER_MINUTE = 180


def reading_minutes(body: str) -> int:
    return max(1, round(len(body.split()) / WORDS_PER_MINUTE))


async def summaries(
    session: AsyncSession, stories: Sequence[Story], seen: Visibility = EVERYTHING
) -> list[StorySummary]:
    """`seen`: covers are never taken from media the reader may not see."""
    if not stories:
        return []
    persons, media = await _links(session, [s.id for s in stories])
    authors = await user_refs(session, [s.author_user_id for s in stories])
    media_ids = {m for ids in media.values() for m in ids}
    files = (
        {
            m.id: m
            for m in await session.scalars(select(MediaFile).where(MediaFile.id.in_(media_ids)))
        }
        if media_ids
        else {}
    )

    def cover(story_id: uuid.UUID) -> str | None:
        for mid in media[story_id]:
            m = None if seen.hides_media(mid) else files.get(mid)
            if m and m.thumb_key and m.kind in (MediaKind.photo, MediaKind.document_scan):
                return file_url(m, "thumb")
        return None

    return [
        StorySummary(
            id=s.id,
            title=s.title,
            excerpt=excerpt(s.body),
            narrator=s.narrator,
            date=PartialDateOut.from_domain(s.date),
            status=s.status,
            author=authors.get(s.author_user_id) if s.author_user_id else None,
            person_ids=persons[s.id],
            updated_at=s.updated_at,
            cover_url=cover(s.id),
            reading_minutes=reading_minutes(s.body),
        )
        for s in stories
    ]


async def story_out(
    session: AsyncSession,
    story: Story,
    user: User,
    role: TreeRole,
    seen: Visibility = EVERYTHING,
) -> StoryOut:
    persons, media = await _links(session, [story.id])
    summary = (await summaries(session, [story], seen))[0]
    names = await summary_map(session, story.tree_id, persons[story.id])
    media_rows = list(
        await session.scalars(select(MediaFile).where(MediaFile.id.in_(media[story.id])))
    )
    return StoryOut(
        **summary.model_dump(),
        body=story.body,
        persons=[names[p] for p in persons[story.id] if p in names],
        media=await media_out_many(session, media_rows),
        review_comment=story.review_comment,
        can_edit=can_edit(story, user, role),
        created_at=story.created_at,
    )


# --- Writing ----------------------------------------------------------------------------


async def create_story(
    session: AsyncSession, tree_id: uuid.UUID, body: StoryCreate, actor: Actor, role: TreeRole
) -> Story:
    assert actor.user is not None
    status = body.status
    if not is_editor(role) and status == StoryStatus.published:
        status = StoryStatus.draft  # contributors cannot publish
    story = Story(
        id=uuid.uuid4(),
        tree_id=tree_id,
        title=body.title.strip(),
        body=body.body or "",
        narrator=body.narrator,
        status=status,
        author_user_id=actor.user.id,
        created_by_id=actor.user.id,
        updated_by_id=actor.user.id,
    )
    set_date(story, "date", "date_sort", to_partial(body.date))
    session.add(story)
    await session.flush()
    await _set_links(session, story, body.person_ids or [], body.media_ids or [])
    audit.record(
        session, actor, "story.create", "story", story.id, tree_id=tree_id,
        after=await snapshot_of(session, story),
    )  # fmt: skip
    await session.commit()
    return story


async def update_story(
    session: AsyncSession, story: Story, body: StoryUpdate, actor: Actor, role: TreeRole
) -> Story:
    assert actor.user is not None
    if not can_edit(story, actor.user, role):
        raise PermissionDeniedError()
    before = await snapshot_of(session, story)
    fields = body.model_fields_set
    if body.title is not None:
        story.title = body.title.strip()
    if "body" in fields:
        story.body = body.body or ""
    if "narrator" in fields:
        story.narrator = body.narrator
    if "date" in fields:
        set_date(story, "date", "date_sort", to_partial(body.date))
    await _set_links(session, story, body.person_ids, body.media_ids)
    story.updated_by_id = actor.user.id
    story.updated_at = utcnow()
    after = await snapshot_of(session, story)
    if before != after:
        audit.record(
            session, actor, "story.update", "story", story.id, tree_id=story.tree_id,
            before=before, after=after,
        )  # fmt: skip
    await session.commit()
    return story


async def change_status(
    session: AsyncSession,
    story: Story,
    action: str,
    actor: Actor,
    role: TreeRole,
    comment: str | None = None,
) -> Story:
    """submit (author: draft → pending_review), publish (editor), return (editor → draft)."""
    assert actor.user is not None
    before = await snapshot_of(session, story)
    if action == "submit":
        if story.author_user_id != actor.user.id and not is_editor(role):
            raise PermissionDeniedError()
        if story.status != StoryStatus.draft:
            raise AppError("invalid_story_status")
        story.status = StoryStatus.pending_review
    elif action in ("publish", "return"):
        if not is_editor(role):
            raise PermissionDeniedError()
        if action == "publish":
            story.status = StoryStatus.published
        else:
            if story.status == StoryStatus.draft:
                raise AppError("invalid_story_status")
            story.status = StoryStatus.draft
        story.review_comment = comment
    story.updated_at = utcnow()
    audit.record(
        session, actor, f"story.{action}", "story", story.id, tree_id=story.tree_id,
        before=before, after=await snapshot_of(session, story),
    )  # fmt: skip
    await session.commit()
    return story


async def delete_story(session: AsyncSession, story: Story, actor: Actor, role: TreeRole) -> None:
    assert actor.user is not None
    if not can_edit(story, actor.user, role):
        raise PermissionDeniedError()
    story.deleted_at, story.deleted_batch_id = utcnow(), story.id
    audit.record(
        session, actor, "story.delete", "story", story.id, tree_id=story.tree_id,
        before=await snapshot_of(session, story),
    )  # fmt: skip
    await session.commit()


async def pending_count(session: AsyncSession, tree_id: uuid.UUID) -> int:
    return (
        await session.scalar(
            select(func.count()).where(
                Story.tree_id == tree_id,
                Story.status == StoryStatus.pending_review,
                Story.deleted_at.is_(None),
            )
        )
        or 0
    )
