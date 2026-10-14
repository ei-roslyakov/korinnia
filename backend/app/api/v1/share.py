"""Share links (D98): admins manage them per tree; anyone with a link opens a read-only view."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Request, Response, status
from pydantic import BaseModel, Field

from app.api.cookies import SHARE_COOKIE, clear_share_cookie, set_share_cookie
from app.api.deps import ActorDep, RealAccount, SessionDep, TreeAdmin
from app.core.errors import NotAuthenticatedError
from app.core.security import utcnow
from app.models import ShareLink, User
from app.services import share_links as service

router = APIRouter(tags=["share links"])

# A visitor's browser remembers an opened link at most this long (or until it expires).
MAX_COOKIE_AGE = timedelta(days=30)


class ShareLinkCreate(BaseModel):
    label: str | None = Field(default=None, max_length=200)
    # None: the link never expires (it can still be revoked).
    expires_in_days: int | None = Field(default=30, ge=1, le=3650)


class ShareLinkOut(BaseModel):
    id: uuid.UUID
    label: str | None
    created_at: datetime
    created_by: str | None
    expires_at: datetime | None
    revoked_at: datetime | None
    last_used_at: datetime | None
    use_count: int
    active: bool


class CreatedShareLink(BaseModel):
    link: ShareLinkOut
    # Shown once: only a hash of the token is stored.
    url: str


class ShareSession(BaseModel):
    tree_id: uuid.UUID
    tree_name: str
    expires_at: datetime | None


async def _out(session: SessionDep, link: ShareLink) -> ShareLinkOut:
    user = await session.get(User, link.created_by_id) if link.created_by_id else None
    return ShareLinkOut(
        id=link.id,
        label=link.label,
        created_at=link.created_at,
        created_by=user.display_name if user else None,
        expires_at=link.expires_at,
        revoked_at=link.revoked_at,
        last_used_at=link.last_used_at,
        use_count=link.use_count,
        active=service.is_usable(link),
    )


@router.get("/trees/{tree_id}/share-links", response_model=list[ShareLinkOut])
async def list_links(access: TreeAdmin, session: SessionDep) -> list[ShareLinkOut]:
    return [await _out(session, link) for link in await service.list_links(session, access.tree.id)]


@router.post(
    "/trees/{tree_id}/share-links",
    response_model=CreatedShareLink,
    status_code=status.HTTP_201_CREATED,
)
async def create_link(
    body: ShareLinkCreate,
    access: TreeAdmin,
    session: SessionDep,
    actor: ActorDep,
    _: RealAccount,
) -> CreatedShareLink:
    """A read-only link to this tree for people without an account."""
    link, token = await service.create_link(
        session, access.tree, label=body.label, expires_in_days=body.expires_in_days, actor=actor
    )
    return CreatedShareLink(link=await _out(session, link), url=service.link_url(token))


@router.delete("/trees/{tree_id}/share-links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_link(
    link_id: uuid.UUID, access: TreeAdmin, session: SessionDep, actor: ActorDep
) -> None:
    await service.revoke(session, await service.get_link(session, access.tree.id, link_id), actor)


@router.post("/share/{token}/open", response_model=ShareSession)
async def open_link(token: str, response: Response, session: SessionDep) -> ShareSession:
    """Open a share link: the browser gets a cookie that lets it view this one tree."""
    link, tree = await service.open_link(session, token)
    age = MAX_COOKIE_AGE
    if link.expires_at is not None:
        age = min(age, link.expires_at - utcnow())
    set_share_cookie(response, token, max_age=age)
    return ShareSession(tree_id=tree.id, tree_name=tree.name, expires_at=link.expires_at)


@router.get("/share/session", response_model=ShareSession)
async def share_session(request: Request, session: SessionDep) -> ShareSession:
    """The tree this browser may view through a share link (401 if none)."""
    found = await service.resolve(session, request.cookies.get(SHARE_COOKIE))
    if found is None:
        raise NotAuthenticatedError("no_share_session")
    link, tree = found
    return ShareSession(tree_id=tree.id, tree_name=tree.name, expires_at=link.expires_at)


@router.post("/share/leave", status_code=status.HTTP_204_NO_CONTENT)
async def leave(response: Response) -> None:
    clear_share_cookie(response)
