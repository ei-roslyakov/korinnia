"""Superadmin endpoints: users, trees, invitations, global audit log, integrity checks."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select

from app.api.deps import ActorDep, PageParams, SessionDep, require_superadmin
from app.core.enums import IntegrityStatus
from app.core.errors import AppError, NotFoundError
from app.core.security import utcnow
from app.models import IntegrityRun, Invitation, MediaFile, Tree
from app.schemas.audit import AuditEntryOut, AuditQuery
from app.schemas.common import Page
from app.schemas.data_safety import IntegrityIssueOut, IntegrityOverview, IntegrityRunOut
from app.schemas.trees import AdminTreeOut
from app.schemas.users import (
    CreatedInvitation,
    CreateInvitationRequest,
    CreateUserRequest,
    InvitationOut,
    LinkResponse,
    UpdateUserRequest,
    UserOut,
)
from app.services import audit, integrity
from app.services import trees as tree_service
from app.services import users as user_service

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_superadmin)])


def invitation_out(inv: Invitation) -> InvitationOut:
    out = InvitationOut.model_validate(inv)
    out.tree_name = inv.tree.name if inv.tree else None
    out.created_by_name = inv.created_by.display_name if inv.created_by else None
    return out


# --- Users ------------------------------------------------------------------------------


@router.get("/users", response_model=Page[UserOut])
async def list_users(
    session: SessionDep,
    page: PageParams,
    q: Annotated[str | None, Query(max_length=200)] = None,
    is_active: bool | None = None,
) -> Page[UserOut]:
    users, total = await user_service.list_users(
        session, q=q, is_active=is_active, limit=page.limit, offset=page.offset
    )
    return Page(
        items=[UserOut.model_validate(u) for u in users],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(body: CreateUserRequest, session: SessionDep, actor: ActorDep) -> UserOut:
    user = await user_service.create_user(
        session,
        email=body.email,
        display_name=body.display_name,
        password=body.password,
        preferred_language=body.preferred_language,
        is_superadmin=body.is_superadmin,
        actor=actor,
    )
    return UserOut.model_validate(user)


@router.get("/users/{user_id}", response_model=UserOut)
async def get_user(user_id: uuid.UUID, session: SessionDep) -> UserOut:
    return UserOut.model_validate(await user_service.get_user(session, user_id))


@router.patch("/users/{user_id}", response_model=UserOut)
async def update_user(
    user_id: uuid.UUID, body: UpdateUserRequest, session: SessionDep, actor: ActorDep
) -> UserOut:
    target = await user_service.get_user(session, user_id)
    user = await user_service.update_user(
        session,
        target,
        display_name=body.display_name,
        preferred_language=body.preferred_language,
        is_active=body.is_active,
        is_superadmin=body.is_superadmin,
        can_create_trees=body.can_create_trees,
        actor=actor,
    )
    return UserOut.model_validate(user)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: uuid.UUID, session: SessionDep, actor: ActorDep) -> None:
    target = await user_service.get_user(session, user_id)
    await user_service.delete_user(session, target, actor)


@router.post("/users/{user_id}/password-reset", response_model=LinkResponse)
async def password_reset_link(
    user_id: uuid.UUID, session: SessionDep, actor: ActorDep
) -> LinkResponse:
    target = await user_service.get_user(session, user_id)
    url, row = await user_service.create_password_reset(session, target, actor)
    return LinkResponse(url=url, expires_at=row.expires_at)


@router.post("/users/{user_id}/disable-2fa", response_model=UserOut)
async def disable_2fa(user_id: uuid.UUID, session: SessionDep, actor: ActorDep) -> UserOut:
    target = await user_service.get_user(session, user_id)
    await user_service.admin_disable_2fa(session, target, actor)
    return UserOut.model_validate(target)


# --- Trees ------------------------------------------------------------------------------


@router.get("/trees", response_model=Page[AdminTreeOut])
async def list_trees(
    session: SessionDep,
    page: PageParams,
    q: Annotated[str | None, Query(max_length=200)] = None,
    deleted: bool = False,
) -> Page[AdminTreeOut]:
    rows, total = await tree_service.list_all_trees(
        session, q=q, deleted=deleted, limit=page.limit, offset=page.offset
    )
    info = await tree_service.overviews(session, [r.tree.id for r in rows])
    return Page(
        items=[
            AdminTreeOut(
                id=r.tree.id,
                name=r.tree.name,
                is_demo=r.tree.is_demo,
                owner_id=r.tree.owner_id,
                owner_name=r.owner.display_name if r.owner else None,
                owner_email=r.owner.email if r.owner else None,
                member_count=r.member_count,
                person_count=info[r.tree.id].person_count,
                created_at=r.tree.created_at,
                deleted_at=r.tree.deleted_at,
            )
            for r in rows
        ],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.post("/trees/{tree_id}/restore", status_code=status.HTTP_204_NO_CONTENT)
async def restore_tree(tree_id: uuid.UUID, session: SessionDep, actor: ActorDep) -> None:
    tree = await tree_service.get_any_tree(session, tree_id)
    await tree_service.restore_tree(session, tree, actor)


# --- Invitations ------------------------------------------------------------------------


@router.get("/invitations", response_model=list[InvitationOut])
async def list_invitations(session: SessionDep) -> list[InvitationOut]:
    return [invitation_out(i) for i in await user_service.list_invitations(session)]


@router.post("/invitations", response_model=CreatedInvitation, status_code=status.HTTP_201_CREATED)
async def create_invitation(
    body: CreateInvitationRequest, session: SessionDep, actor: ActorDep
) -> CreatedInvitation:
    tree = await session.get(Tree, body.tree_id) if body.tree_id else None
    if body.tree_id and (tree is None or tree.deleted_at is not None):
        raise NotFoundError("tree_not_found")
    inv, url = await user_service.create_invitation(
        session,
        email=body.email,
        tree=tree,
        role=body.role,
        is_superadmin=body.is_superadmin,
        actor=actor,
    )
    return CreatedInvitation(invitation=invitation_out(inv), url=url)


@router.delete("/invitations/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_invitation(invitation_id: uuid.UUID, session: SessionDep, actor: ActorDep) -> None:
    inv = await user_service.get_invitation(session, invitation_id)
    await user_service.revoke_invitation(session, inv, actor)


# --- Audit log --------------------------------------------------------------------------


@router.get("/audit-log", response_model=Page[AuditEntryOut])
async def audit_log(
    session: SessionDep, page: PageParams, q: Annotated[AuditQuery, Query()]
) -> Page[AuditEntryOut]:
    rows, total = await audit.list_entries(session, q, limit=page.limit, offset=page.offset)
    return Page(
        items=[AuditEntryOut.model_validate(r) for r in rows],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get("/audit-log/actions", response_model=list[str])
async def audit_actions(session: SessionDep) -> list[str]:
    return await audit.list_actions(session)


# --- Integrity of stored originals -------------------------------------------------------


async def _run_out(session: SessionDep, run: IntegrityRun) -> IntegrityRunOut:
    return IntegrityRunOut(
        id=run.id,
        status=run.status,
        trigger=run.trigger,
        triggered_by=await integrity.user_label(session, run.triggered_by_id),
        started_at=run.started_at,
        finished_at=run.finished_at,
        files_checked=run.files_checked,
        bytes_checked=run.bytes_checked,
        problems=run.problems,
        untracked_files=run.untracked_files,
        error=run.error,
    )


@router.get("/integrity", response_model=IntegrityOverview)
async def integrity_overview(session: SessionDep) -> IntegrityOverview:
    runs = await integrity.latest_runs(session)
    finished = next((r for r in runs if r.finished_at is not None), None)
    issues = await integrity.run_issues(session, finished.id) if finished else []
    trees = {
        t.id: t.name
        for t in await session.scalars(
            select(Tree).where(Tree.id.in_({i.tree_id for i in issues if i.tree_id}))
        )
    }
    media = {
        m.id: m
        for m in await session.scalars(
            select(MediaFile).where(MediaFile.id.in_({i.media_id for i in issues if i.media_id}))
        )
    }
    files, size = await integrity.originals_total(session)
    return IntegrityOverview(
        total_files=files,
        total_bytes=size,
        runs=[await _run_out(session, r) for r in runs],
        issues=[
            IntegrityIssueOut(
                key=i.key,
                problem=i.problem,
                media_id=i.media_id,
                tree_id=i.tree_id,
                tree_name=trees.get(i.tree_id) if i.tree_id else None,
                filename=(
                    (media[i.media_id].title or media[i.media_id].original_filename)
                    if i.media_id in media
                    else None
                ),
                expected_size=i.expected_size,
                actual_size=i.actual_size,
                expected_sha256=i.expected_sha256,
                actual_sha256=i.actual_sha256,
            )
            for i in issues
        ],
    )


@router.post("/integrity/run", response_model=IntegrityRunOut, status_code=202)
async def start_integrity_check(session: SessionDep, actor: ActorDep) -> IntegrityRunOut:
    from app.jobs.queue import enqueue_integrity_check

    run = await integrity.start_run(session, trigger="manual", actor=actor)
    try:
        await enqueue_integrity_check(run.id)
    except Exception as exc:
        run.status = IntegrityStatus.failed
        run.error = "could not queue the check"
        run.finished_at = utcnow()
        await session.commit()
        raise AppError("job_queue_unavailable", status_code=503) from exc
    return await _run_out(session, run)
