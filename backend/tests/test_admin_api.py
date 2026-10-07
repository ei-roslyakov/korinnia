from __future__ import annotations

from collections.abc import Awaitable, Callable

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, User
from tests.conftest import ApiClient
from tests.helpers import totp_code

MakeUser = Callable[..., Awaitable[User]]
MakeClient = Callable[[], Awaitable[ApiClient]]


async def _admin(make_user: MakeUser, make_client: MakeClient) -> tuple[ApiClient, User]:
    root = await make_user("root@example.com", is_superadmin=True, name="Root")
    c = await make_client()
    await c.login("root@example.com")
    return c, root


async def test_user_crud(
    make_user: MakeUser, make_client: MakeClient, session: AsyncSession
) -> None:
    admin, _ = await _admin(make_user, make_client)
    resp = await admin.post(
        "/api/v1/admin/users",
        json={"email": "Taras@Example.com", "display_name": "Тарас", "password": "long-password-1"},
    )
    assert resp.status_code == 201
    user = resp.json()
    assert user["email"] == "taras@example.com"
    assert user["preferred_language"] == "en"  # the installation default (DEFAULT_LANGUAGE)
    resp = await admin.post(
        "/api/v1/admin/users",
        json={"email": "taras@example.com", "display_name": "Dup", "password": "long-password-1"},
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == "email_taken"

    listing = (await admin.get("/api/v1/admin/users?q=тар")).json()
    assert [u["email"] for u in listing["items"]] == ["taras@example.com"]
    assert (await admin.get("/api/v1/admin/users?is_active=false")).json()["total"] == 0
    assert (await admin.get(f"/api/v1/admin/users/{user['id']}")).status_code == 200

    resp = await admin.patch(
        f"/api/v1/admin/users/{user['id']}", json={"display_name": "Taras", "is_superadmin": True}
    )
    assert resp.json()["is_superadmin"] is True
    entry = (await session.scalars(select(AuditLog).where(AuditLog.action == "user.update"))).one()
    assert entry.before == {"display_name": "Тарас", "is_superadmin": False}
    assert "password_hash" not in (entry.after or {})

    assert (await admin.delete(f"/api/v1/admin/users/{user['id']}")).status_code == 204
    assert (await admin.get(f"/api/v1/admin/users/{user['id']}")).status_code == 404


async def test_superadmin_safety_rails(make_user: MakeUser, make_client: MakeClient) -> None:
    admin, root = await _admin(make_user, make_client)
    resp = await admin.patch(f"/api/v1/admin/users/{root.id}", json={"is_active": False})
    assert resp.json()["code"] == "cannot_demote_self"
    assert (await admin.delete(f"/api/v1/admin/users/{root.id}")).json()[
        "code"
    ] == "cannot_delete_self"

    # Another superadmin cannot remove the last *active* superadmin either.
    other = await make_user("other@example.com", is_superadmin=True)
    oc = await make_client()
    await oc.login("other@example.com")
    assert (
        await oc.patch(f"/api/v1/admin/users/{root.id}", json={"is_superadmin": False})
    ).status_code == 200
    resp = await admin.get("/api/v1/admin/users")  # root is no longer superadmin
    assert resp.status_code == 403
    resp = await oc.delete(f"/api/v1/admin/users/{other.id}")
    assert resp.json()["code"] == "cannot_delete_self"


async def test_last_superadmin_cannot_be_deleted_by_peer(
    make_user: MakeUser, make_client: MakeClient
) -> None:
    admin, _ = await _admin(make_user, make_client)
    inactive = await make_user("inactive@example.com", is_superadmin=True, is_active=False)
    # Deleting an inactive superadmin is fine; root remains.
    assert (await admin.delete(f"/api/v1/admin/users/{inactive.id}")).status_code == 204


async def test_admin_disables_2fa(make_user: MakeUser, make_client: MakeClient) -> None:
    admin, _ = await _admin(make_user, make_client)
    target = await make_user("lost@example.com")
    c = await make_client()
    await c.login("lost@example.com")
    secret = (await c.post("/api/v1/auth/2fa/setup")).json()["secret"]
    await c.post("/api/v1/auth/2fa/enable", json={"code": totp_code(secret)})
    resp = await admin.post(f"/api/v1/admin/users/{target.id}/disable-2fa")
    assert resp.json()["totp_enabled"] is False
    fresh = await make_client()
    assert (await fresh.login("lost@example.com"))["status"] == "ok"


async def test_invitations_admin(make_user: MakeUser, make_client: MakeClient) -> None:
    admin, _ = await _admin(make_user, make_client)
    await make_user("exists@example.com")
    resp = await admin.post(
        "/api/v1/admin/invitations", json={"email": "exists@example.com", "is_superadmin": True}
    )
    assert resp.json()["code"] == "email_taken"
    resp = await admin.post("/api/v1/admin/invitations", json={"email": "a@example.com"})
    assert resp.status_code == 422  # needs a tree+role or superadmin
    resp = await admin.post(
        "/api/v1/admin/invitations",
        json={
            "email": "a@example.com",
            "tree_id": "00000000-0000-0000-0000-000000000000",
            "role": "viewer",
        },
    )
    assert resp.json()["code"] == "tree_not_found"

    first = await admin.post(
        "/api/v1/admin/invitations", json={"email": "new-admin@example.com", "is_superadmin": True}
    )
    assert first.status_code == 201
    second = await admin.post(
        "/api/v1/admin/invitations", json={"email": "new-admin@example.com", "is_superadmin": True}
    )
    pending = (await admin.get("/api/v1/admin/invitations")).json()
    assert [p["id"] for p in pending] == [second.json()["invitation"]["id"]]  # re-invite replaces
    assert pending[0]["created_by_name"] == "Root"

    inv_id = pending[0]["id"]
    assert (await admin.delete(f"/api/v1/admin/invitations/{inv_id}")).status_code == 204
    assert (
        await admin.delete(f"/api/v1/admin/invitations/{inv_id}")
    ).status_code == 204  # idempotent
    assert (await admin.get("/api/v1/admin/invitations")).json() == []
    resp = await admin.delete("/api/v1/admin/invitations/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404

    # Accepted invitations cannot be revoked; superadmin flag carries over.
    third = (
        await admin.post(
            "/api/v1/admin/invitations", json={"email": "sa2@example.com", "is_superadmin": True}
        )
    ).json()
    guest = await make_client()
    body = (
        await guest.post(
            f"/api/v1/auth/invitations/{third['url'].rsplit('/', 1)[-1]}/accept",
            json={"display_name": "SA2", "password": "long-password-1"},
        )
    ).json()
    assert body["user"]["is_superadmin"] is True
    resp = await admin.delete(f"/api/v1/admin/invitations/{third['invitation']['id']}")
    assert resp.json()["code"] == "invitation_already_accepted"


async def test_audit_log_filters(make_user: MakeUser, make_client: MakeClient) -> None:
    admin, root = await _admin(make_user, make_client)
    await admin.post(
        "/api/v1/admin/users",
        json={"email": "u@example.com", "display_name": "U", "password": "long-password-1"},
    )
    page = (await admin.get("/api/v1/admin/audit-log?action=user.create&limit=1")).json()
    assert page["total"] == 2  # root (factory) + u
    assert len(page["items"]) == 1
    mine = (await admin.get(f"/api/v1/admin/audit-log?user_id={root.id}")).json()
    assert {e["action"] for e in mine["items"]} == {"user.create", "auth.login"}
    future = (await admin.get("/api/v1/admin/audit-log?date_from=2999-01-01T00:00:00Z")).json()
    assert future["total"] == 0
    past = (await admin.get("/api/v1/admin/audit-log?date_to=2000-01-01T00:00:00Z")).json()
    assert past["total"] == 0
    by_entity = (
        await admin.get(f"/api/v1/admin/audit-log?entity_type=user&entity_id={root.id}")
    ).json()
    assert by_entity["total"] >= 1
    actions = (await admin.get("/api/v1/admin/audit-log/actions")).json()
    assert "user.create" in actions
    assert (await admin.get("/api/v1/admin/audit-log?limit=500")).status_code == 422


async def test_new_users_get_the_installation_language(
    make_user: MakeUser, make_client: MakeClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.config import get_settings

    admin, _ = await _admin(make_user, make_client)
    monkeypatch.setattr(get_settings(), "default_language", "uk")
    resp = await admin.post(
        "/api/v1/admin/users",
        json={"email": "olena@example.com", "display_name": "Олена", "password": "long-password-1"},
    )
    assert resp.json()["preferred_language"] == "uk"
    resp = await admin.post(
        "/api/v1/admin/users",
        json={
            "email": "anna@example.com",
            "display_name": "Anna",
            "password": "long-password-1",
            "preferred_language": "pl",
        },
    )
    assert resp.json()["preferred_language"] == "pl"  # an explicit choice wins
