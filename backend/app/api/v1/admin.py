"""Superadmin endpoints: users, invitations, global audit log."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import ActorDep, PageParams, SessionDep, require_superadmin
from app.core.errors import NotFoundError
from app.models import Invitation, Tree
from app.schemas.audit import AuditEntryOut, AuditQuery
from app.schemas.common import Page
from app.schemas.users import (
    CreatedInvitation,
    CreateInvitationRequest,
    CreateUserRequest,
    InvitationOut,
    LinkResponse,
    UpdateUserRequest,
    UserOut,
)
from app.services import audit
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
