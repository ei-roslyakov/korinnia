"""Shared FastAPI dependencies: DB session, current user, authorization by tree role."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.cookies import ACCESS_COOKIE, SHARE_COOKIE
from app.core.db import get_session
from app.core.errors import NotAuthenticatedError, NotFoundError, PermissionDeniedError
from app.core.security import TokenError, decode_token
from app.models import Tree, TreeRole, User
from app.services.auth import session_revoked
from app.services.context import Actor
from app.services.share_links import resolve as resolve_share_link
from app.services.trees import get_tree_role

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


async def get_current_user(request: Request, session: SessionDep) -> User:
    token = request.cookies.get(ACCESS_COOKIE)
    if not token:
        raise NotAuthenticatedError()
    try:
        payload = decode_token(token, "access")
    except TokenError as exc:
        raise NotAuthenticatedError(exc.code) from exc
    user = await session.get(User, payload.sub)
    if user is None or not user.is_active or session_revoked(user, payload.iat):
        raise NotAuthenticatedError("token_revoked")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def require_real_account(user: CurrentUser) -> User:
    """Refuse demo accounts: nothing that reaches other people (sharing) or outlives the
    demo (two-step verification, passwords)."""
    if user.is_sandbox:
        raise PermissionDeniedError("not_in_demo")
    return user


RealAccount = Annotated[User, Depends(require_real_account)]


def get_actor(request: Request, user: CurrentUser) -> Actor:
    return Actor(user, client_ip(request), request.headers.get("user-agent"))


def get_anonymous_actor(request: Request) -> Actor:
    return Actor(None, client_ip(request), request.headers.get("user-agent"))


ActorDep = Annotated[Actor, Depends(get_actor)]
AnonymousActor = Annotated[Actor, Depends(get_anonymous_actor)]


async def require_superadmin(user: CurrentUser) -> User:
    if not user.is_superadmin:
        raise PermissionDeniedError()
    return user


Superadmin = Annotated[User, Depends(require_superadmin)]


@dataclass(frozen=True, slots=True)
class TreeAccess:
    tree: Tree
    role: TreeRole
    user: User


def _share_guest() -> User:
    """Who a share-link visitor is to the services: nobody in particular (never stored)."""
    return User(
        id=uuid.UUID(int=0),
        email="",
        display_name="",
        is_superadmin=False,
        is_active=True,
        totp_enabled=False,
    )


def tree_access(min_role: TreeRole) -> Callable[..., Awaitable[TreeAccess]]:
    """Dependency factory: the current user must have at least `min_role` in `tree_id`.

    Non-members get 404 (the tree's existence is not revealed); members with a lower role
    get 403. Without a signed-in user, a share-link cookie for this very tree gives viewer
    access to read-only (GET) requests (D98).
    """

    async def dependency(tree_id: uuid.UUID, request: Request, session: SessionDep) -> TreeAccess:
        async def via_share_link(user: User | None) -> TreeAccess | None:
            shared = await resolve_share_link(session, request.cookies.get(SHARE_COOKIE))
            if shared is None or shared[1].id != tree_id:
                return None
            if request.method not in ("GET", "HEAD") or min_role != TreeRole.viewer:
                raise PermissionDeniedError()
            return TreeAccess(tree=shared[1], role=TreeRole.viewer, user=user or _share_guest())

        if not request.cookies.get(ACCESS_COOKIE):
            guest = await via_share_link(None)
            if guest is None:
                raise NotAuthenticatedError()
            return guest
        user = await get_current_user(request, session)
        found = await get_tree_role(session, tree_id, user)
        if found is None:
            # Not a member: a share link opened in this browser still lets them look.
            shared = await via_share_link(user)
            if shared is None:
                raise NotFoundError("tree_not_found")
            return shared
        tree, role = found
        if not role.at_least(min_role):
            raise PermissionDeniedError()
        return TreeAccess(tree=tree, role=role, user=user)

    return dependency


TreeViewer = Annotated[TreeAccess, Depends(tree_access(TreeRole.viewer))]
TreeContributor = Annotated[TreeAccess, Depends(tree_access(TreeRole.contributor))]
TreeEditor = Annotated[TreeAccess, Depends(tree_access(TreeRole.editor))]
TreeAdmin = Annotated[TreeAccess, Depends(tree_access(TreeRole.admin))]


@dataclass(frozen=True, slots=True)
class Pagination:
    limit: int
    offset: int


def pagination(
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Pagination:
    return Pagination(limit=limit, offset=offset)


PageParams = Annotated[Pagination, Depends(pagination)]
