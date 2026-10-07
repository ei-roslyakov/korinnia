"""Trees and membership management (per-tree roles)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import (
    ActorDep,
    CurrentUser,
    PageParams,
    SessionDep,
    Superadmin,
    TreeAdmin,
    TreeViewer,
)
from app.api.v1.admin import invitation_out
from app.core.errors import NotFoundError
from app.models import Tree, TreeMembership, TreeRole, User
from app.schemas.audit import AuditEntryOut, AuditQuery
from app.schemas.common import Page
from app.schemas.trees import (
    AddMemberRequest,
    AddMemberResponse,
    CreateTreeRequest,
    MemberOut,
    MembersResponse,
    TreeOut,
    UpdateMemberRequest,
    UpdateTreeRequest,
)
from app.services import audit
from app.services import trees as tree_service
from app.services import users as user_service

router = APIRouter(prefix="/trees", tags=["trees"])


def tree_out(tree: Tree, role: TreeRole) -> TreeOut:
    return TreeOut(
        id=tree.id,
        name=tree.name,
        description=tree.description,
        owner_id=tree.owner_id,
        created_at=tree.created_at,
        updated_at=tree.updated_at,
        my_role=role,
    )


def member_out(membership: TreeMembership, user: User) -> MemberOut:
    return MemberOut(
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=membership.role,
        is_active=user.is_active,
        created_at=membership.created_at,
    )


@router.get("", response_model=list[TreeOut])
async def list_trees(user: CurrentUser, session: SessionDep) -> list[TreeOut]:
    return [tree_out(t, r) for t, r in await tree_service.list_trees_for_user(session, user)]


@router.post("", response_model=TreeOut, status_code=status.HTTP_201_CREATED)
async def create_tree(
    body: CreateTreeRequest, session: SessionDep, actor: ActorDep, _: Superadmin
) -> TreeOut:
    assert actor.user is not None
    owner = await user_service.get_user(session, body.owner_id) if body.owner_id else actor.user
    tree = await tree_service.create_tree(
        session, name=body.name, description=body.description, owner=owner, actor=actor
    )
    return tree_out(tree, TreeRole.admin)


@router.get("/{tree_id}", response_model=TreeOut)
async def get_tree(access: TreeViewer) -> TreeOut:
    return tree_out(access.tree, access.role)


@router.patch("/{tree_id}", response_model=TreeOut)
async def update_tree(
    body: UpdateTreeRequest, access: TreeAdmin, session: SessionDep, actor: ActorDep
) -> TreeOut:
    tree = await tree_service.update_tree(
        session,
        access.tree,
        name=body.name,
        description=body.description,
        fields_set=body.model_fields_set,
        actor=actor,
    )
    return tree_out(tree, access.role)


@router.delete("/{tree_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tree(
    access: TreeAdmin, session: SessionDep, actor: ActorDep, _: Superadmin
) -> None:
    await tree_service.delete_tree(session, access.tree, actor)


# --- Members ----------------------------------------------------------------------------


@router.get("/{tree_id}/members", response_model=MembersResponse)
async def list_members(access: TreeAdmin, session: SessionDep) -> MembersResponse:
    members = await tree_service.list_members(session, access.tree)
    invitations = await user_service.list_invitations(session, tree_id=access.tree.id)
    return MembersResponse(
        members=[member_out(m, u) for m, u in members],
        invitations=[invitation_out(i) for i in invitations],
    )


@router.post("/{tree_id}/members", response_model=AddMemberResponse, status_code=201)
async def add_member(
    body: AddMemberRequest, access: TreeAdmin, session: SessionDep, actor: ActorDep
) -> AddMemberResponse:
    membership, user, inv, url = await tree_service.add_member_or_invite(
        session, access.tree, email=body.email, role=body.role, actor=actor
    )
    if membership is not None and user is not None:
        return AddMemberResponse(kind="member", member=member_out(membership, user))
    assert inv is not None
    return AddMemberResponse(kind="invitation", invitation=invitation_out(inv), url=url)


@router.patch("/{tree_id}/members/{user_id}", response_model=MemberOut)
async def update_member(
    user_id: uuid.UUID,
    body: UpdateMemberRequest,
    access: TreeAdmin,
    session: SessionDep,
    actor: ActorDep,
) -> MemberOut:
    membership = await tree_service.get_membership(session, access.tree, user_id)
    membership = await tree_service.update_member_role(session, membership, body.role, actor)
    return member_out(membership, membership.user)


@router.delete("/{tree_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    user_id: uuid.UUID, access: TreeAdmin, session: SessionDep, actor: ActorDep
) -> None:
    membership = await tree_service.get_membership(session, access.tree, user_id)
    await tree_service.remove_member(session, membership, actor)


@router.delete("/{tree_id}/invitations/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_invitation(
    invitation_id: uuid.UUID, access: TreeAdmin, session: SessionDep, actor: ActorDep
) -> None:
    inv = await user_service.get_invitation(session, invitation_id)
    if inv.tree_id != access.tree.id:
        raise NotFoundError("invitation_not_found")
    await user_service.revoke_invitation(session, inv, actor)


# --- Tree audit log ---------------------------------------------------------------------


@router.get("/{tree_id}/audit-log", response_model=Page[AuditEntryOut])
async def tree_audit_log(
    access: TreeAdmin,
    session: SessionDep,
    page: PageParams,
    q: Annotated[AuditQuery, Query()],
) -> Page[AuditEntryOut]:
    q = q.model_copy(update={"tree_id": access.tree.id})
    rows, total = await audit.list_entries(session, q, limit=page.limit, offset=page.offset)
    return Page(
        items=[AuditEntryOut.model_validate(r) for r in rows],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )
