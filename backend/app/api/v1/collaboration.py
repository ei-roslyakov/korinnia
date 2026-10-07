"""Edit suggestions, moderation queue, comments, open questions, data quality."""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, status

from app.api.deps import ActorDep, SessionDep, TreeContributor, TreeEditor, TreeViewer
from app.models import CommentTarget, QuestionStatus, SuggestionStatus
from app.schemas.collaboration import (
    CommentCreate,
    CommentOut,
    CommentUpdate,
    DataQuality,
    ModerationCounts,
    QuestionCreate,
    QuestionOut,
    QuestionUpdate,
    SuggestionCreate,
    SuggestionOut,
)
from app.schemas.stories import ReviewIn
from app.services.genealogy import collaboration as svc
from app.services.genealogy import stories as story_service
from app.services.genealogy.quality import data_quality

router = APIRouter(prefix="/trees/{tree_id}", tags=["collaboration"])


# --- Suggestions & moderation -----------------------------------------------------------


@router.post("/suggestions", response_model=SuggestionOut, status_code=status.HTTP_201_CREATED)
async def create_suggestion(
    body: SuggestionCreate, access: TreeContributor, session: SessionDep, actor: ActorDep
) -> SuggestionOut:
    """Propose a change to a person or event; an editor approves or rejects it."""
    s = await svc.create_suggestion(session, access.tree.id, body, actor)
    return (await svc.suggestions_out(session, [s]))[0]


@router.get("/suggestions", response_model=list[SuggestionOut])
async def list_suggestions(
    access: TreeContributor,
    session: SessionDep,
    status: SuggestionStatus | None = None,
    entity_id: uuid.UUID | None = None,
) -> list[SuggestionOut]:
    """Editors see all suggestions; contributors see their own."""
    rows = await svc.list_suggestions(
        session, access.tree.id, access.user, access.role, status=status, entity_id=entity_id
    )
    return await svc.suggestions_out(session, rows)


@router.post("/suggestions/{suggestion_id}/{decision}", response_model=SuggestionOut)
async def review_suggestion(
    suggestion_id: uuid.UUID,
    decision: Literal["approve", "reject"],
    access: TreeEditor,
    session: SessionDep,
    actor: ActorDep,
    body: ReviewIn | None = None,
) -> SuggestionOut:
    s = await svc.get_suggestion(session, access.tree.id, suggestion_id)
    s = await svc.review_suggestion(
        session,
        s,
        approve=decision == "approve",
        comment=body.comment if body else None,
        actor=actor,
    )
    return (await svc.suggestions_out(session, [s]))[0]


@router.get("/moderation", response_model=ModerationCounts)
async def moderation_counts(access: TreeEditor, session: SessionDep) -> ModerationCounts:
    return ModerationCounts(
        suggestions=await svc.pending_suggestions(session, access.tree.id),
        stories=await story_service.pending_count(session, access.tree.id),
    )


# --- Comments ---------------------------------------------------------------------------


@router.get("/comments", response_model=list[CommentOut])
async def list_comments(
    entity_type: CommentTarget, entity_id: uuid.UUID, access: TreeViewer, session: SessionDep
) -> list[CommentOut]:
    rows = await svc.list_comments(
        session, access.tree.id, entity_type, entity_id, access.user, access.role
    )
    return await svc.comments_out(session, rows)


@router.post("/comments", response_model=CommentOut, status_code=status.HTTP_201_CREATED)
async def create_comment(
    body: CommentCreate, access: TreeContributor, session: SessionDep, actor: ActorDep
) -> CommentOut:
    c = await svc.create_comment(session, access.tree.id, body, actor, access.role)
    return (await svc.comments_out(session, [c]))[0]


@router.patch("/comments/{comment_id}", response_model=CommentOut)
async def update_comment(
    comment_id: uuid.UUID,
    body: CommentUpdate,
    access: TreeContributor,
    session: SessionDep,
    actor: ActorDep,
) -> CommentOut:
    c = await svc.get_comment(session, access.tree.id, comment_id)
    return (
        await svc.comments_out(session, [await svc.update_comment(session, c, body.body, actor)])
    )[0]


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(
    comment_id: uuid.UUID, access: TreeContributor, session: SessionDep, actor: ActorDep
) -> None:
    """Authors delete their own comments; editors may delete any (moderation)."""
    c = await svc.get_comment(session, access.tree.id, comment_id)
    await svc.delete_comment(session, c, actor, access.role)


# --- Open questions ---------------------------------------------------------------------


@router.get("/questions", response_model=list[QuestionOut])
async def list_questions(
    access: TreeViewer,
    session: SessionDep,
    person_id: uuid.UUID | None = None,
    status: QuestionStatus | None = None,
) -> list[QuestionOut]:
    rows = await svc.list_questions(session, access.tree.id, person_id=person_id, status=status)
    return await svc.questions_out(session, rows)


@router.post("/questions", response_model=QuestionOut, status_code=status.HTTP_201_CREATED)
async def create_question(
    body: QuestionCreate, access: TreeContributor, session: SessionDep, actor: ActorDep
) -> QuestionOut:
    q = await svc.create_question(session, access.tree.id, body, actor)
    return (await svc.questions_out(session, [q]))[0]


@router.patch("/questions/{question_id}", response_model=QuestionOut)
async def update_question(
    question_id: uuid.UUID,
    body: QuestionUpdate,
    access: TreeContributor,
    session: SessionDep,
    actor: ActorDep,
) -> QuestionOut:
    q = await svc.get_question(session, access.tree.id, question_id)
    return (await svc.questions_out(session, [await svc.update_question(session, q, body, actor)]))[
        0
    ]


@router.delete("/questions/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_question(
    question_id: uuid.UUID, access: TreeContributor, session: SessionDep, actor: ActorDep
) -> None:
    q = await svc.get_question(session, access.tree.id, question_id)
    await svc.delete_question(session, q, actor, access.role)


# --- Data quality -----------------------------------------------------------------------


@router.get("/data-quality", response_model=DataQuality)
async def get_data_quality(access: TreeContributor, session: SessionDep) -> DataQuality:
    """Research to-do list: missing birth dates, photos, sources; date conflicts; questions."""
    return await data_quality(session, access.tree.id)
