"""Stories (contributors write, editors publish)."""

from __future__ import annotations

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Query, status

from app.api.deps import (
    ActorDep,
    PageParams,
    SessionDep,
    TreeContributor,
    TreeViewer,
    VisibilityDep,
)
from app.core.errors import NotFoundError
from app.models import StoryKind, StoryStatus
from app.schemas.common import Page
from app.schemas.stories import ReviewIn, StoryCreate, StoryOut, StorySummary, StoryUpdate
from app.services.genealogy import stories as svc

router = APIRouter(prefix="/trees/{tree_id}/stories", tags=["stories"])


@router.get("", response_model=Page[StorySummary])
async def list_stories(
    access: TreeViewer,
    session: SessionDep,
    page: PageParams,
    seen: VisibilityDep,
    person_id: uuid.UUID | None = None,
    status: StoryStatus | None = None,
    kind: Annotated[list[StoryKind] | None, Query(max_length=3)] = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
) -> Page[StorySummary]:
    """Published stories; plus your own drafts; editors see all. `kind` (repeatable) keeps
    stories, recipes or traditions; `q` searches titles, texts, narrators, occasions and
    recipes' ingredients."""
    rows, total = await svc.list_stories(
        session, access.tree.id, access.user, access.role,
        person_id=person_id, status=status, limit=page.limit, offset=page.offset,
        hidden=seen.protected, kinds=kind or (), q=q,
    )  # fmt: skip
    return Page(
        items=await svc.summaries(session, rows, seen),
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.post("", response_model=StoryOut, status_code=status.HTTP_201_CREATED)
async def create_story(
    body: StoryCreate, access: TreeContributor, session: SessionDep, actor: ActorDep
) -> StoryOut:
    story = await svc.create_story(session, access.tree.id, body, actor, access.role)
    return await svc.story_out(session, story, access.user, access.role)


@router.get("/{story_id}", response_model=StoryOut)
async def get_story(
    story_id: uuid.UUID, access: TreeViewer, session: SessionDep, seen: VisibilityDep
) -> StoryOut:
    story = await svc.get_story(session, access.tree.id, story_id, access.user, access.role)
    out = await svc.story_out(session, story, access.user, access.role, seen)
    if seen.hides_story(out.person_ids):
        raise NotFoundError("story_not_found")
    return seen.redact(out)


@router.patch("/{story_id}", response_model=StoryOut)
async def update_story(
    story_id: uuid.UUID,
    body: StoryUpdate,
    access: TreeContributor,
    session: SessionDep,
    actor: ActorDep,
) -> StoryOut:
    story = await svc.get_story(session, access.tree.id, story_id, access.user, access.role)
    story = await svc.update_story(session, story, body, actor, access.role)
    return await svc.story_out(session, story, access.user, access.role)


@router.post("/{story_id}/{action}", response_model=StoryOut)
async def change_status(
    story_id: uuid.UUID,
    action: Literal["submit", "publish", "return"],
    access: TreeContributor,
    session: SessionDep,
    actor: ActorDep,
    body: ReviewIn | None = None,
) -> StoryOut:
    """submit (author → review), publish (editor), return (editor → draft, with comment)."""
    story = await svc.get_story(session, access.tree.id, story_id, access.user, access.role)
    story = await svc.change_status(
        session, story, action, actor, access.role, body.comment if body else None
    )
    return await svc.story_out(session, story, access.user, access.role)


@router.delete("/{story_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_story(
    story_id: uuid.UUID, access: TreeContributor, session: SessionDep, actor: ActorDep
) -> None:
    story = await svc.get_story(session, access.tree.id, story_id, access.user, access.role)
    await svc.delete_story(session, story, actor, access.role)
