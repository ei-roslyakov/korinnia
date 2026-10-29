"""Edit suggestions (moderated), comments and open research questions."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, NotFoundError, PermissionDeniedError
from app.core.security import utcnow
from app.models import (
    Comment,
    CommentTarget,
    EditSuggestion,
    Event,
    MediaFile,
    OpenQuestion,
    Person,
    QuestionStatus,
    Story,
    StoryPerson,
    SuggestionStatus,
    SuggestionTarget,
    TreeRole,
    User,
)
from app.schemas.collaboration import (
    CommentCreate,
    CommentOut,
    QuestionCreate,
    QuestionOut,
    QuestionUpdate,
    SuggestionCreate,
    SuggestionOut,
)
from app.schemas.events import EventUpdate
from app.schemas.persons import PersonUpdate
from app.services import audit
from app.services.context import Actor
from app.services.genealogy import events as event_service
from app.services.genealogy import persons as person_service
from app.services.genealogy import stories as story_service
from app.services.genealogy.common import get_live
from app.services.genealogy.snapshots import event_snapshot
from app.services.genealogy.sources import user_refs
from app.services.genealogy.summaries import summary_map
from app.services.visibility import Visibility

# --- Suggestions ------------------------------------------------------------------------

# What a contributor may propose (photos, portraits and relationships stay with editors).
PERSON_SUGGESTIBLE = {
    "gender",
    "is_living",
    "short_summary",
    "biography",
    "occupation",
    "education",
    "religion",
    "nationality",
    "notes_for_descendants",
    "research_status",
    "names",
    "birth",
    "death",
}


def _validate_patch(entity_type: SuggestionTarget, patch: dict[str, Any]) -> dict[str, Any]:
    if not patch:
        raise AppError("empty_suggestion")
    try:
        if entity_type == SuggestionTarget.person:
            unknown = set(patch) - PERSON_SUGGESTIBLE
            if unknown:
                raise AppError("field_not_suggestible", extra={"fields": sorted(unknown)})
            model: PersonUpdate | EventUpdate = PersonUpdate.model_validate(patch)
        else:
            model = EventUpdate.model_validate(patch)
    except ValidationError as exc:
        raise AppError(
            "invalid_suggestion",
            extra={"errors": exc.errors(include_url=False, include_context=False)},
        ) from exc
    return model.model_dump(mode="json", exclude_unset=True)


async def _target(
    session: AsyncSession, tree_id: uuid.UUID, s: SuggestionTarget, eid: uuid.UUID
) -> Any:
    if s == SuggestionTarget.person:
        return await person_service.get_person(session, tree_id, eid)
    return await event_service.get_event(session, tree_id, eid)


async def create_suggestion(
    session: AsyncSession, tree_id: uuid.UUID, body: SuggestionCreate, actor: Actor
) -> EditSuggestion:
    assert actor.user is not None
    await _target(session, tree_id, body.entity_type, body.entity_id)
    s = EditSuggestion(
        tree_id=tree_id,
        entity_type=body.entity_type,
        entity_id=body.entity_id,
        patch=_validate_patch(body.entity_type, body.patch),
        comment=body.comment,
        created_by_id=actor.user.id,
    )
    session.add(s)
    await session.flush()
    audit.record(
        session, actor, "suggestion.create", "suggestion", s.id, tree_id=tree_id,
        after={"entity_type": s.entity_type.value, "entity_id": str(s.entity_id), "patch": s.patch},
    )  # fmt: skip
    await session.commit()
    return s


async def get_suggestion(
    session: AsyncSession, tree_id: uuid.UUID, sid: uuid.UUID
) -> EditSuggestion:
    s = await session.get(EditSuggestion, sid)
    if s is None or s.tree_id != tree_id:
        raise NotFoundError("suggestion_not_found")
    return s


async def list_suggestions(
    session: AsyncSession,
    tree_id: uuid.UUID,
    user: User,
    role: TreeRole,
    *,
    status: SuggestionStatus | None,
    entity_id: uuid.UUID | None = None,
) -> list[EditSuggestion]:
    stmt = select(EditSuggestion).where(EditSuggestion.tree_id == tree_id)
    if not role.at_least(TreeRole.editor):
        stmt = stmt.where(EditSuggestion.created_by_id == user.id)  # contributors: own only
    if status:
        stmt = stmt.where(EditSuggestion.status == status)
    if entity_id:
        stmt = stmt.where(EditSuggestion.entity_id == entity_id)
    return list(await session.scalars(stmt.order_by(EditSuggestion.created_at.desc())))


async def _current_values(session: AsyncSession, s: EditSuggestion) -> tuple[str, dict[str, Any]]:
    if s.entity_type == SuggestionTarget.person:
        person = await session.get(Person, s.entity_id)
        if person is None:
            return "?", {}
        snap = await person_service.snapshot_of(session, person)
        names = await summary_map(session, person.tree_id, [person.id])
        label = names[person.id].display_name if person.id in names else "?"
        return label, {k: snap.get(k) for k in s.patch}
    event = await session.get(Event, s.entity_id)
    if event is None:
        return "?", {}
    await session.refresh(event, ["participants"])
    snap = event_snapshot(event)
    return event.type.value, {k: snap.get(k) for k in s.patch}


async def suggestions_out(
    session: AsyncSession, items: Sequence[EditSuggestion]
) -> list[SuggestionOut]:
    users = await user_refs(
        session, [s.created_by_id for s in items] + [s.reviewed_by_id for s in items]
    )
    out = []
    for s in items:
        label, current = await _current_values(session, s)
        out.append(
            SuggestionOut(
                id=s.id,
                entity_type=s.entity_type,
                entity_id=s.entity_id,
                entity_label=label,
                patch=s.patch,
                current=current,
                comment=s.comment,
                status=s.status,
                author=users.get(s.created_by_id) if s.created_by_id else None,
                reviewer=users.get(s.reviewed_by_id) if s.reviewed_by_id else None,
                review_comment=s.review_comment,
                reviewed_at=s.reviewed_at,
                created_at=s.created_at,
            )
        )
    return out


async def review_suggestion(
    session: AsyncSession,
    s: EditSuggestion,
    *,
    approve: bool,
    comment: str | None,
    actor: Actor,
) -> EditSuggestion:
    """Approve (apply the patch as the reviewing editor) or reject."""
    assert actor.user is not None
    if s.status != SuggestionStatus.pending:
        raise AppError("suggestion_already_reviewed")
    if approve:
        target = await _target(session, s.tree_id, s.entity_type, s.entity_id)
        # Re-validate: the data may have changed since the suggestion was made.
        patch = _validate_patch(s.entity_type, s.patch)
        if s.entity_type == SuggestionTarget.person:
            await person_service.update_person(
                session, target, PersonUpdate.model_validate(patch), actor
            )
        else:
            await event_service.update_event(
                session, target, EventUpdate.model_validate(patch), actor
            )
    s.status = SuggestionStatus.approved if approve else SuggestionStatus.rejected
    s.reviewed_by_id = actor.user.id
    s.reviewed_at = utcnow()
    s.review_comment = comment
    audit.record(
        session, actor, f"suggestion.{'approve' if approve else 'reject'}", "suggestion", s.id,
        tree_id=s.tree_id, after={"status": s.status.value, "comment": comment},
    )  # fmt: skip
    await session.commit()
    return s


async def pending_suggestions(session: AsyncSession, tree_id: uuid.UUID) -> int:
    return (
        await session.scalar(
            select(func.count()).where(
                EditSuggestion.tree_id == tree_id, EditSuggestion.status == SuggestionStatus.pending
            )
        )
        or 0
    )


# --- Comments ---------------------------------------------------------------------------


async def _check_comment_target(
    session: AsyncSession,
    tree_id: uuid.UUID,
    target: CommentTarget,
    entity_id: uuid.UUID,
    user: User,
    role: TreeRole,
) -> None:
    if target == CommentTarget.person:
        await get_live(session, Person, tree_id, entity_id, "comment_target_not_found")
    elif target == CommentTarget.media:
        await get_live(session, MediaFile, tree_id, entity_id, "comment_target_not_found")
    else:
        story = await get_live(session, Story, tree_id, entity_id, "comment_target_not_found")
        if not story_service.can_view(story, user, role):
            raise NotFoundError("comment_target_not_found")


async def comment_target_hidden(
    session: AsyncSession, target: CommentTarget, entity_id: uuid.UUID, seen: Visibility
) -> bool:
    if not seen.restricted:
        return False
    if target == CommentTarget.person:
        return seen.hides_person(entity_id)
    if target == CommentTarget.media:
        return seen.hides_media(entity_id)
    about = list(
        await session.scalars(
            select(StoryPerson.person_id)
            .join(Person, Person.id == StoryPerson.person_id)
            .where(StoryPerson.story_id == entity_id, Person.deleted_at.is_(None))
        )
    )
    return seen.hides_story(about)


async def list_comments(
    session: AsyncSession,
    tree_id: uuid.UUID,
    target: CommentTarget,
    entity_id: uuid.UUID,
    user: User,
    role: TreeRole,
) -> list[Comment]:
    await _check_comment_target(session, tree_id, target, entity_id, user, role)
    return list(
        await session.scalars(
            select(Comment)
            .where(
                Comment.tree_id == tree_id,
                Comment.entity_type == target,
                Comment.entity_id == entity_id,
                Comment.deleted_at.is_(None),
            )
            .order_by(Comment.created_at)
        )
    )


async def comments_out(session: AsyncSession, items: Sequence[Comment]) -> list[CommentOut]:
    users = await user_refs(session, [c.author_id for c in items])
    return [
        CommentOut(
            id=c.id,
            entity_type=c.entity_type,
            entity_id=c.entity_id,
            body=c.body,
            author=users.get(c.author_id) if c.author_id else None,
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c in items
    ]


async def create_comment(
    session: AsyncSession, tree_id: uuid.UUID, body: CommentCreate, actor: Actor, role: TreeRole
) -> Comment:
    assert actor.user is not None
    await _check_comment_target(
        session, tree_id, body.entity_type, body.entity_id, actor.user, role
    )
    c = Comment(
        tree_id=tree_id,
        entity_type=body.entity_type,
        entity_id=body.entity_id,
        body=body.body.strip(),
        author_id=actor.user.id,
    )
    session.add(c)
    await session.flush()
    audit.record(
        session, actor, "comment.create", "comment", c.id, tree_id=tree_id,
        after={"entity_type": c.entity_type.value, "entity_id": str(c.entity_id), "body": c.body},
    )  # fmt: skip
    await session.commit()
    return c


async def get_comment(session: AsyncSession, tree_id: uuid.UUID, cid: uuid.UUID) -> Comment:
    c = await session.get(Comment, cid)
    if c is None or c.tree_id != tree_id or c.deleted_at is not None:
        raise NotFoundError("comment_not_found")
    return c


async def update_comment(session: AsyncSession, c: Comment, text: str, actor: Actor) -> Comment:
    if actor.user is None or c.author_id != actor.user.id:
        raise PermissionDeniedError()
    before = {"body": c.body}
    c.body = text.strip()
    c.updated_at = utcnow()
    audit.record(
        session, actor, "comment.update", "comment", c.id, tree_id=c.tree_id,
        before=before, after={"body": c.body},
    )  # fmt: skip
    await session.commit()
    return c


async def delete_comment(session: AsyncSession, c: Comment, actor: Actor, role: TreeRole) -> None:
    """Authors delete their own comments; editors moderate any comment."""
    if actor.user is None or (c.author_id != actor.user.id and not role.at_least(TreeRole.editor)):
        raise PermissionDeniedError()
    c.deleted_at = utcnow()
    audit.record(
        session,
        actor,
        "comment.delete",
        "comment",
        c.id,
        tree_id=c.tree_id,
        before={"body": c.body},
    )
    await session.commit()


# --- Open questions ---------------------------------------------------------------------


async def questions_out(session: AsyncSession, items: Sequence[OpenQuestion]) -> list[QuestionOut]:
    if not items:
        return []
    names = await summary_map(session, items[0].tree_id, {q.person_id for q in items})
    users = await user_refs(session, [q.created_by_id for q in items])
    return [
        QuestionOut(
            id=q.id,
            person_id=q.person_id,
            person_name=names[q.person_id].display_name if q.person_id in names else "?",
            question=q.question,
            notes=q.notes,
            status=q.status,
            resolution=q.resolution,
            resolved_at=q.resolved_at,
            created_by=users.get(q.created_by_id) if q.created_by_id else None,
            created_at=q.created_at,
        )
        for q in items
    ]


async def list_questions(
    session: AsyncSession,
    tree_id: uuid.UUID,
    *,
    person_id: uuid.UUID | None = None,
    status: QuestionStatus | None = None,
    limit: int | None = None,
) -> list[OpenQuestion]:
    stmt = (
        select(OpenQuestion)
        .join(Person, Person.id == OpenQuestion.person_id)
        .where(OpenQuestion.tree_id == tree_id, Person.deleted_at.is_(None))
    )
    if person_id:
        stmt = stmt.where(OpenQuestion.person_id == person_id)
    if status:
        stmt = stmt.where(OpenQuestion.status == status)
    stmt = stmt.order_by(OpenQuestion.status, OpenQuestion.created_at.desc())
    if limit:
        stmt = stmt.limit(limit)
    return list(await session.scalars(stmt))


def _question_snapshot(q: OpenQuestion) -> dict[str, Any]:
    return {
        "person_id": str(q.person_id),
        "question": q.question,
        "notes": q.notes,
        "status": q.status.value,
        "resolution": q.resolution,
    }


async def create_question(
    session: AsyncSession, tree_id: uuid.UUID, body: QuestionCreate, actor: Actor
) -> OpenQuestion:
    await get_live(session, Person, tree_id, body.person_id, "person_not_found")
    q = OpenQuestion(
        tree_id=tree_id,
        person_id=body.person_id,
        question=body.question.strip(),
        notes=body.notes,
        created_by_id=actor.user.id if actor.user else None,
    )
    session.add(q)
    await session.flush()
    audit.record(
        session, actor, "question.create", "question", q.id, tree_id=tree_id,
        after=_question_snapshot(q),
    )  # fmt: skip
    await session.commit()
    return q


async def get_question(session: AsyncSession, tree_id: uuid.UUID, qid: uuid.UUID) -> OpenQuestion:
    q = await session.get(OpenQuestion, qid)
    if q is None or q.tree_id != tree_id:
        raise NotFoundError("question_not_found")
    return q


async def update_question(
    session: AsyncSession, q: OpenQuestion, body: QuestionUpdate, actor: Actor
) -> OpenQuestion:
    before = _question_snapshot(q)
    fields = body.model_fields_set
    if body.question is not None:
        q.question = body.question.strip()
    for f in ("notes", "resolution"):
        if f in fields:
            setattr(q, f, getattr(body, f))
    if body.status is not None and body.status != q.status:
        q.status = body.status
        q.resolved_at = utcnow() if body.status == QuestionStatus.resolved else None
    q.updated_at = utcnow()
    audit.record(
        session, actor, "question.update", "question", q.id, tree_id=q.tree_id,
        before=before, after=_question_snapshot(q),
    )  # fmt: skip
    await session.commit()
    return q


async def delete_question(
    session: AsyncSession, q: OpenQuestion, actor: Actor, role: TreeRole
) -> None:
    if actor.user is None or (
        q.created_by_id != actor.user.id and not role.at_least(TreeRole.editor)
    ):
        raise PermissionDeniedError()
    audit.record(
        session, actor, "question.delete", "question", q.id, tree_id=q.tree_id,
        before=_question_snapshot(q),
    )  # fmt: skip
    await session.delete(q)
    await session.commit()
