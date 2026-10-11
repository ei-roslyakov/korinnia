from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, Tree, TreeRole, User
from app.services import trees as tree_service
from tests.conftest import ApiClient
from tests.helpers import Ctx

MakeUser = Callable[..., Awaitable[User]]
MakeClient = Callable[[], Awaitable[ApiClient]]


async def _superadmin(make_user: MakeUser, make_client: MakeClient) -> ApiClient:
    await make_user("root@example.com", is_superadmin=True)
    c = await make_client()
    await c.login("root@example.com")
    return c


async def test_create_update_delete_tree(
    make_user: MakeUser, make_client: MakeClient, session: AsyncSession
) -> None:
    sa = await _superadmin(make_user, make_client)
    owner = await make_user("owner@example.com")
    resp = await sa.post(
        "/api/v1/trees",
        json={"name": " Родина Коваленків ", "description": "Полтава", "owner_id": str(owner.id)},
    )
    assert resp.status_code == 201
    tree = resp.json()
    assert tree["name"] == "Родина Коваленків"
    assert tree["owner_id"] == str(owner.id)

    oc = await make_client()
    me = await oc.login("owner@example.com")
    assert me["user"]["trees"][0]["role"] == "admin"

    resp = await oc.patch(f"/api/v1/trees/{tree['id']}", json={"description": None})
    assert resp.status_code == 200
    assert resp.json()["description"] is None
    entries = (
        await session.scalars(select(AuditLog).where(AuditLog.action == "tree.update"))
    ).all()
    assert entries[0].before == {"description": "Полтава"}
    assert entries[0].after == {"description": None}

    assert (await sa.delete(f"/api/v1/trees/{tree['id']}")).status_code == 204
    assert (await oc.get(f"/api/v1/trees/{tree['id']}")).status_code == 404
    assert (await session.get(Tree, tree["id"])) is not None  # soft delete only


async def test_create_tree_with_unknown_owner(make_user: MakeUser, make_client: MakeClient) -> None:
    sa = await _superadmin(make_user, make_client)
    resp = await sa.post(
        "/api/v1/trees",
        json={"name": "X", "owner_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert resp.status_code == 404


async def test_member_management(
    make_user: MakeUser,
    make_client: MakeClient,
    make_tree: Callable[..., Awaitable[Tree]],
    add_member: Callable[..., Awaitable[Any]],
) -> None:
    owner = await make_user("owner@example.com")
    tree = await make_tree(owner)
    cousin = await make_user("cousin@example.com", name="Cousin")
    admin = await make_client()
    await admin.login("owner@example.com")
    base = f"/api/v1/trees/{tree.id}"

    # Existing user -> added directly.
    resp = await admin.post(
        f"{base}/members", json={"email": "COUSIN@example.com", "role": "editor"}
    )
    assert resp.status_code == 201
    assert resp.json()["kind"] == "member"
    assert resp.json()["member"]["role"] == "editor"
    resp = await admin.post(
        f"{base}/members", json={"email": "cousin@example.com", "role": "viewer"}
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == "already_member"

    # Unknown email -> invitation link.
    resp = await admin.post(f"{base}/members", json={"email": "aunt@example.com", "role": "viewer"})
    assert resp.json()["kind"] == "invitation"
    assert "/invite/" in resp.json()["url"]
    inv_id = resp.json()["invitation"]["id"]

    members = (await admin.get(f"{base}/members")).json()
    assert {m["email"]: m["role"] for m in members["members"]} == {
        "owner@example.com": "admin",
        "cousin@example.com": "editor",
    }
    assert [i["email"] for i in members["invitations"]] == ["aunt@example.com"]

    assert (await admin.delete(f"{base}/invitations/{inv_id}")).status_code == 204
    assert (await admin.get(f"{base}/members")).json()["invitations"] == []

    resp = await admin.patch(f"{base}/members/{cousin.id}", json={"role": "admin"})
    assert resp.json()["role"] == "admin"
    resp = await admin.patch(f"{base}/members/{cousin.id}", json={"role": "admin"})
    assert resp.status_code == 200
    assert (await admin.delete(f"{base}/members/{cousin.id}")).status_code == 204
    resp = await admin.delete(f"{base}/members/{cousin.id}")
    assert resp.status_code == 404


async def test_last_admin_is_protected(
    make_user: MakeUser, make_client: MakeClient, make_tree: Callable[..., Awaitable[Tree]]
) -> None:
    owner = await make_user("owner@example.com")
    tree = await make_tree(owner)
    admin = await make_client()
    await admin.login("owner@example.com")
    base = f"/api/v1/trees/{tree.id}"
    resp = await admin.patch(f"{base}/members/{owner.id}", json={"role": "editor"})
    assert resp.status_code == 400
    assert resp.json()["code"] == "last_tree_admin"
    resp = await admin.delete(f"{base}/members/{owner.id}")
    assert resp.json()["code"] == "last_tree_admin"


async def test_invitation_for_other_tree_cannot_be_revoked(
    make_user: MakeUser, make_client: MakeClient, make_tree: Callable[..., Awaitable[Tree]]
) -> None:
    a_owner = await make_user("a@example.com")
    b_owner = await make_user("b@example.com")
    tree_a, tree_b = await make_tree(a_owner, "A"), await make_tree(b_owner, "B")
    b = await make_client()
    await b.login("b@example.com")
    inv = (
        await b.post(
            f"/api/v1/trees/{tree_b.id}/members", json={"email": "z@example.com", "role": "viewer"}
        )
    ).json()["invitation"]
    a = await make_client()
    await a.login("a@example.com")
    resp = await a.delete(f"/api/v1/trees/{tree_a.id}/invitations/{inv['id']}")
    assert resp.status_code == 404


async def test_tree_audit_log_is_scoped(
    make_user: MakeUser, make_client: MakeClient, make_tree: Callable[..., Awaitable[Tree]]
) -> None:
    owner = await make_user("owner@example.com")
    tree = await make_tree(owner)
    await make_tree(owner, "Unrelated")
    c = await make_client()
    await c.login("owner@example.com")
    await c.patch(f"/api/v1/trees/{tree.id}", json={"name": "Renamed"})
    page = (await c.get(f"/api/v1/trees/{tree.id}/audit-log")).json()
    assert {e["tree_id"] for e in page["items"]} == {str(tree.id)}
    assert [e["action"] for e in page["items"]] == ["tree.update", "tree.create"]
    filtered = (await c.get(f"/api/v1/trees/{tree.id}/audit-log?action=tree.create")).json()
    assert filtered["total"] == 1


async def test_accepting_invitation_for_deleted_tree_fails(
    make_user: MakeUser,
    make_client: MakeClient,
    session: AsyncSession,
    make_tree: Callable[..., Awaitable[Tree]],
) -> None:
    sa = await _superadmin(make_user, make_client)
    owner = await make_user("owner@example.com")
    tree = await make_tree(owner)
    url = (
        await sa.post(
            f"/api/v1/trees/{tree.id}/members", json={"email": "late@example.com", "role": "viewer"}
        )
    ).json()["url"]
    await sa.delete(f"/api/v1/trees/{tree.id}")
    guest = await make_client()
    assert (
        await guest.get(f"/api/v1/auth/invitations/{url.rsplit('/', 1)[-1]}")
    ).status_code == 404
    assert TreeRole.admin.at_least(TreeRole.editor)
    assert not TreeRole.viewer.at_least(TreeRole.contributor)


async def test_tree_list_overview(ctx: Ctx, session: AsyncSession) -> None:
    from app.models import Person

    a = await ctx.person("Іван", birth={"date": {"year": 1890}})
    await ctx.person("Марія", birth={"date": {"year": 1925}}, death={"date": {"year": 1990}})
    row = await session.get(Person, uuid.UUID(a["id"]))
    assert row is not None
    row.avatar_key = f"avatars/{ctx.tree.id}/{a['id']}/x.webp"
    await session.commit()

    trees = (await ctx.editor.get("/api/v1/trees")).json()
    t = next(x for x in trees if x["id"] == str(ctx.tree.id))
    assert (t["person_count"], t["first_year"], t["last_year"]) == (2, 1890, 1990)
    assert len(t["cover"]) == 1
    assert t["cover"][0].startswith(f"/api/v1/trees/{ctx.tree.id}/persons/{a['id']}/avatar")


async def test_tree_admin_can_delete_their_tree(
    make_user: MakeUser,
    make_client: MakeClient,
    make_tree: Callable[..., Awaitable[Tree]],
    add_member: Callable[..., Awaitable[Any]],
) -> None:
    owner = await make_user("owner@example.com")
    tree = await make_tree(owner)
    await add_member(tree, await make_user("ed@example.com"), TreeRole.editor)
    ed = await make_client()
    await ed.login("ed@example.com")
    assert (await ed.delete(f"/api/v1/trees/{tree.id}")).status_code == 403

    oc = await make_client()
    await oc.login("owner@example.com")
    assert (await oc.delete(f"/api/v1/trees/{tree.id}")).status_code == 204
    assert (await oc.get("/api/v1/trees")).json() == []
    assert (await ed.get(f"/api/v1/trees/{tree.id}")).status_code == 404


async def test_admin_lists_deletes_and_restores_trees(
    make_user: MakeUser,
    make_client: MakeClient,
    session: AsyncSession,
    make_tree: Callable[..., Awaitable[Tree]],
) -> None:
    sa = await _superadmin(make_user, make_client)
    owner = await make_user("owner@example.com", name="Owner")
    tree = await make_tree(owner, "Коваленки")
    await make_tree(owner, "Ткачуки")

    page = (await sa.get("/api/v1/admin/trees", params={"q": "КОВАЛ"})).json()
    assert page["total"] == 1
    row = page["items"][0]
    assert (row["name"], row["owner_email"], row["member_count"]) == (
        "Коваленки",
        "owner@example.com",
        1,
    )
    assert row["deleted_at"] is None
    assert (await sa.get("/api/v1/admin/trees", params={"q": "OWNER@"})).json()["total"] == 2

    assert (await sa.delete(f"/api/v1/trees/{tree.id}")).status_code == 204
    assert (await sa.get("/api/v1/admin/trees")).json()["total"] == 1
    deleted = (await sa.get("/api/v1/admin/trees", params={"deleted": True})).json()["items"]
    assert [d["id"] for d in deleted] == [str(tree.id)]
    assert deleted[0]["deleted_at"] is not None

    assert (await sa.post(f"/api/v1/admin/trees/{tree.id}/restore")).status_code == 204
    assert (await sa.get(f"/api/v1/trees/{tree.id}")).status_code == 200
    actions = (await session.scalars(select(AuditLog.action))).all()
    assert {"tree.delete", "tree.restore"} <= set(actions)

    # Only for superadmins.
    oc = await make_client()
    await oc.login("owner@example.com")
    assert (await oc.get("/api/v1/admin/trees")).status_code == 403
    assert (await oc.post(f"/api/v1/admin/trees/{tree.id}/restore")).status_code == 403


async def test_restore_demo_tree_when_owner_has_a_new_one(
    make_user: MakeUser, make_client: MakeClient, session: AsyncSession
) -> None:
    from app.services.context import Actor

    sa = await _superadmin(make_user, make_client)
    owner = await make_user("owner@example.com")
    old = await tree_service.create_tree(
        session, name="Demo", description=None, owner=owner, actor=Actor(None), is_demo=True
    )
    await tree_service.delete_tree(session, old, Actor(None))
    await tree_service.create_tree(
        session, name="Demo", description=None, owner=owner, actor=Actor(None), is_demo=True
    )
    resp = await sa.post(f"/api/v1/admin/trees/{old.id}/restore")
    assert resp.status_code == 409
    assert resp.json()["code"] == "demo_tree_exists"


async def test_share_with_an_existing_user_only(
    make_user: MakeUser,
    make_client: MakeClient,
    session: AsyncSession,
    make_tree: Callable[..., Awaitable[Tree]],
    add_member: Callable[..., Awaitable[Any]],
) -> None:
    owner = await make_user("owner@example.com")
    tree = await make_tree(owner)
    cousin = await make_user("cousin@example.com", name="Cousin")
    oc = await make_client()
    await oc.login("owner@example.com")
    base = f"/api/v1/trees/{tree.id}/members"

    # Nobody has this email: an error, and no invitation is created.
    resp = await oc.post(
        base, json={"email": "nobody@example.com", "role": "viewer", "invite": False}
    )
    assert (resp.status_code, resp.json()["code"]) == (404, "no_user_with_email")
    assert (await oc.get(base)).json()["invitations"] == []

    resp = await oc.post(
        base, json={"email": "Cousin@Example.com", "role": "editor", "invite": False}
    )
    assert resp.status_code == 201
    assert resp.json()["kind"] == "member"
    assert resp.json()["member"]["display_name"] == "Cousin"
    cc = await make_client()
    await cc.login("cousin@example.com")
    assert (await cc.get(f"/api/v1/trees/{tree.id}")).json()["my_role"] == "editor"

    # Sharing again, or with yourself, says so.
    resp = await oc.post(
        base, json={"email": "cousin@example.com", "role": "viewer", "invite": False}
    )
    assert resp.json()["code"] == "already_member"
    # Only the tree's admins can share it.
    assert cousin.id
    resp = await cc.post(
        base, json={"email": "owner@example.com", "role": "viewer", "invite": False}
    )
    assert resp.status_code == 403
