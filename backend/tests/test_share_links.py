"""Read-only share links (D98)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, ShareLink, Tree, TreeRole, User
from tests.conftest import ApiClient
from tests.helpers import Ctx

MakeUser = Callable[..., Awaitable[User]]
MakeClient = Callable[[], Awaitable[ApiClient]]


def _token(url: str) -> str:
    return url.rsplit("/s/", 1)[1]


async def test_a_link_gives_read_only_access_to_one_tree(
    ctx: Ctx,
    make_client: MakeClient,
    make_user: MakeUser,
    make_tree: Callable[..., Awaitable[Tree]],
    session: AsyncSession,
) -> None:
    person = await ctx.person("Галина", birth={"date": {"year": 1923}})
    created = await ctx.editor.post(
        f"{ctx.base}/share-links", json={"label": "Для тітки", "expires_in_days": 7}
    )
    assert created.status_code == 201, created.text
    url = created.json()["url"]
    assert "/s/" in url
    link = created.json()["link"]
    assert (link["label"], link["active"], link["use_count"]) == ("Для тітки", True, 0)
    # Only a hash of the token is stored.
    row = await session.get(ShareLink, link["id"])
    assert row is not None
    assert _token(url) not in row.token_hash

    guest = await make_client()  # not signed in
    assert (await guest.get(f"{ctx.base}/graph")).status_code == 401
    opened = await guest.post(f"/api/v1/share/{_token(url)}/open")
    assert opened.status_code == 200
    assert opened.json()["tree_id"] == str(ctx.tree.id)
    assert (await guest.get("/api/v1/share/session")).json()["tree_name"] == ctx.tree.name

    # Reading works…
    tree = (await guest.get(ctx.base)).json()
    assert tree["my_role"] == "viewer"
    assert len((await guest.get(f"{ctx.base}/graph")).json()["persons"]) == 1
    assert (await guest.get(f"{ctx.base}/persons/{person['id']}")).status_code == 200
    assert (await guest.get(f"{ctx.base}/timeline")).status_code == 200
    # …changing anything does not, and nothing else is reachable.
    resp = await guest.patch(f"{ctx.base}/persons/{person['id']}", json={"biography": "x"})
    assert resp.status_code == 403
    assert (await guest.post(f"{ctx.base}/persons", json={"names": []})).status_code == 403
    assert (await guest.get(f"{ctx.base}/members")).status_code == 403
    other = await make_tree(await make_user("other@example.com"), "Інша родина")
    assert (await guest.get(f"/api/v1/trees/{other.id}")).status_code == 401
    assert (await guest.get("/api/v1/auth/me")).status_code == 401
    assert (await guest.get("/api/v1/trees")).status_code == 401

    links = (await ctx.editor.get(f"{ctx.base}/share-links")).json()
    assert links[0]["use_count"] == 1
    assert links[0]["last_used_at"] is not None

    # Revoking ends it at once, even for a browser that already opened it.
    assert (await ctx.editor.delete(f"{ctx.base}/share-links/{link['id']}")).status_code == 204
    assert (await guest.get(f"{ctx.base}/graph")).status_code == 401
    again = await guest.post(f"/api/v1/share/{_token(url)}/open")
    assert (again.status_code, again.json()["code"]) == (404, "share_link_invalid")
    assert (await ctx.editor.get(f"{ctx.base}/share-links")).json()[0]["active"] is False
    actions = set((await session.scalars(select(AuditLog.action))).all())
    assert {"share_link.create", "share_link.revoke"} <= actions


async def test_expired_links_and_who_may_create_them(
    ctx: Ctx,
    make_client: MakeClient,
    make_user: MakeUser,
    add_member: Callable[..., Awaitable[Any]],
    session: AsyncSession,
) -> None:
    url = (await ctx.editor.post(f"{ctx.base}/share-links", json={})).json()["url"]
    row = (await session.scalars(select(ShareLink))).one()
    assert row.expires_at is not None  # 30 days by default
    row.expires_at = row.expires_at - timedelta(days=31)
    await session.commit()
    guest = await make_client()
    assert (await guest.post(f"/api/v1/share/{_token(url)}/open")).status_code == 404
    assert (await guest.post("/api/v1/share/nonsense/open")).status_code == 404

    never = await ctx.editor.post(f"{ctx.base}/share-links", json={"expires_in_days": None})
    assert never.json()["link"]["expires_at"] is None

    editor = await make_user("editor@example.com")
    await add_member(ctx.tree, editor, TreeRole.editor)
    e = await make_client()
    await e.login("editor@example.com")
    assert (await e.post(f"{ctx.base}/share-links", json={})).status_code == 403
    assert (await e.get(f"{ctx.base}/share-links")).status_code == 403


async def test_a_signed_in_non_member_can_view_through_a_link(
    ctx: Ctx, make_client: MakeClient, make_user: MakeUser
) -> None:
    url = (await ctx.editor.post(f"{ctx.base}/share-links", json={})).json()["url"]
    await make_user("cousin@example.com")
    cousin = await make_client()
    await cousin.login("cousin@example.com")
    assert (await cousin.get(ctx.base)).status_code == 404  # not a member
    await cousin.post(f"/api/v1/share/{_token(url)}/open")
    resp = await cousin.get(ctx.base)
    assert (resp.status_code, resp.json()["my_role"]) == (200, "viewer")
    assert (await cousin.patch(ctx.base, json={"name": "Моя"})).status_code == 403
    # Leaving forgets the link.
    await cousin.post("/api/v1/share/leave")
    assert (await cousin.get(ctx.base)).status_code == 404
