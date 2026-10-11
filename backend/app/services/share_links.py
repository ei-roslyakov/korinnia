"""Read-only share links (D98): a tree's admins create a link; whoever opens it can view that
tree — and only view it — without an account, until the link expires or is revoked."""

from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import NotFoundError
from app.core.security import generate_url_token, hash_token, utcnow
from app.models import ShareLink, Tree
from app.services import audit
from app.services.context import Actor


def link_url(token: str) -> str:
    return f"{get_settings().public_base_url.rstrip('/')}/s/{token}"


async def create_link(
    session: AsyncSession,
    tree: Tree,
    *,
    label: str | None,
    expires_in_days: int | None,
    actor: Actor,
) -> tuple[ShareLink, str]:
    token = generate_url_token()
    link = ShareLink(
        id=uuid.uuid4(),
        tree_id=tree.id,
        token_hash=hash_token(token),
        label=(label or "").strip() or None,
        created_by_id=actor.user.id if actor.user else None,
        expires_at=utcnow() + timedelta(days=expires_in_days) if expires_in_days else None,
        use_count=0,
    )
    session.add(link)
    audit.record(
        session,
        actor,
        "share_link.create",
        "share_link",
        link.id,
        tree_id=tree.id,
        after={"label": link.label, "expires_in_days": expires_in_days},
    )
    await session.commit()
    return link, token


async def list_links(session: AsyncSession, tree_id: uuid.UUID) -> list[ShareLink]:
    """Usable links first, then the 20 most recent revoked or expired ones."""
    links = list(
        await session.scalars(
            select(ShareLink)
            .where(ShareLink.tree_id == tree_id)
            .order_by(ShareLink.created_at.desc())
        )
    )
    usable = [link for link in links if is_usable(link)]
    return usable + [link for link in links if not is_usable(link)][:20]


def is_usable(link: ShareLink) -> bool:
    return link.revoked_at is None and (link.expires_at is None or link.expires_at > utcnow())


async def get_link(session: AsyncSession, tree_id: uuid.UUID, link_id: uuid.UUID) -> ShareLink:
    link = await session.get(ShareLink, link_id)
    if link is None or link.tree_id != tree_id:
        raise NotFoundError("share_link_not_found")
    return link


async def revoke(session: AsyncSession, link: ShareLink, actor: Actor) -> None:
    if link.revoked_at is None:
        link.revoked_at = utcnow()
        audit.record(
            session, actor, "share_link.revoke", "share_link", link.id, tree_id=link.tree_id
        )
        await session.commit()


async def resolve(session: AsyncSession, token: str | None) -> tuple[ShareLink, Tree] | None:
    """The link and its tree, if the token belongs to a usable link of a live tree."""
    if not token or len(token) > 100:
        return None
    link = await session.scalar(select(ShareLink).where(ShareLink.token_hash == hash_token(token)))
    if link is None or not is_usable(link):
        return None
    tree = await session.get(Tree, link.tree_id)
    if tree is None or tree.deleted_at is not None:
        return None
    return link, tree


async def open_link(session: AsyncSession, token: str) -> tuple[ShareLink, Tree]:
    found = await resolve(session, token)
    if found is None:
        raise NotFoundError("share_link_invalid")
    link, tree = found
    link.use_count += 1
    link.last_used_at = utcnow()
    await session.commit()
    return link, tree
