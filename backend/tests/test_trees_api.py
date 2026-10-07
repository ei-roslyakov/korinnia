from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, Tree, TreeRole, User
from tests.conftest import ApiClient

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
