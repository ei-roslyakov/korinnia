"""Stories (contributors write, editors publish)."""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, status

from app.api.deps import ActorDep, PageParams, SessionDep, TreeContributor, TreeViewer
from app.models import StoryStatus
from app.schemas.common import Page
from app.schemas.stories import ReviewIn, StoryCreate, StoryOut, StorySummary, StoryUpdate
from app.services.genealogy import stories as svc

router = APIRouter(prefix="/trees/{tree_id}/stories", tags=["stories"])


@router.get("", response_model=Page[StorySummary])
async def list_stories(
    access: TreeViewer,
    session: SessionDep,
    page: PageParams,
    person_id: uuid.UUID | None = None,
    status: StoryStatus | None = None,
) -> Page[StorySummary]:
    """Published stories; plus your own drafts; editors see all."""
    rows, total = await svc.list_stories(
        session, access.tree.id, access.user, access.role,
        person_id=person_id, status=status, limit=page.limit, offset=page.offset,
    )  # fmt: skip
    return Page(
        items=await svc.summaries(session, rows), total=total, limit=page.limit, offset=page.offset
    )


@router.post("", response_model=StoryOut, status_code=status.HTTP_201_CREATED)
async def create_story(
    body: StoryCreate, access: TreeContributor, session: SessionDep, actor: ActorDep
) -> StoryOut:
    story = await svc.create_story(session, access.tree.id, body, actor, access.role)
    return await svc.story_out(session, story, access.user, access.role)


@router.get("/{story_id}", response_model=StoryOut)
async def get_story(story_id: uuid.UUID, access: TreeViewer, session: SessionDep) -> StoryOut:
    story = await svc.get_story(session, access.tree.id, story_id, access.user, access.role)
    return await svc.story_out(session, story, access.user, access.role)


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
