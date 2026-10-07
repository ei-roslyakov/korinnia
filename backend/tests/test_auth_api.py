from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.cookies import ACCESS_COOKIE, MFA_COOKIE, REFRESH_COOKIE
from app.core.security import create_token
from app.models import AuditLog, RefreshToken, User
from tests.conftest import PASSWORD, ApiClient
from tests.helpers import totp_code

MakeUser = Callable[..., Awaitable[User]]
MakeClient = Callable[[], Awaitable[ApiClient]]


async def test_mutations_require_csrf(client: ApiClient) -> None:
    del client.headers["X-CSRF-Token"]
    resp = await client.post("/api/v1/auth/login", json={"email": "a@b.cz", "password": "x"})
    assert resp.status_code == 403
    assert resp.json()["code"] == "csrf_failed"
    client.headers["X-CSRF-Token"] = "wrong"
    resp = await client.post("/api/v1/auth/login", json={"email": "a@b.cz", "password": "x"})
    assert resp.status_code == 403


async def test_csrf_endpoint_matches_cookie(make_client: MakeClient) -> None:
    c = await make_client()
    token = (await c.get("/api/v1/auth/csrf")).json()["csrf_token"]
    assert token == c.cookies["korinnia_csrf"]


async def test_login_me_logout(
    client: ApiClient, make_user: MakeUser, session: AsyncSession
) -> None:
    user = await make_user("Halyna@Example.com")
    body = await client.login("halyna@example.com")
    assert body["status"] == "ok"
    assert body["user"]["email"] == "halyna@example.com"
    assert client.cookies.get(ACCESS_COOKIE)
    assert client.cookies.get(REFRESH_COOKIE)

    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["id"] == str(user.id)
    await session.refresh(user)
    assert user.last_login_at is not None

    assert (await client.post("/api/v1/auth/logout")).status_code == 204
    assert (await client.get("/api/v1/auth/me")).status_code == 401
    assert (await client.post("/api/v1/auth/refresh")).status_code == 401
    actions = (await session.scalars(select(AuditLog.action))).all()
    assert "auth.login" in actions


@pytest.mark.parametrize(
    ("email", "password", "code"),
    [
        ("user@example.com", "wrong-password", "invalid_credentials"),
        ("nobody@example.com", PASSWORD, "invalid_credentials"),
    ],
)
async def test_login_failures(
    client: ApiClient, make_user: MakeUser, email: str, password: str, code: str
) -> None:
    await make_user("user@example.com")
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 401
    assert resp.json()["code"] == code


async def test_login_inactive_user(client: ApiClient, make_user: MakeUser) -> None:
    await make_user("old@example.com", is_active=False)
    resp = await client.post(
        "/api/v1/auth/login", json={"email": "old@example.com", "password": PASSWORD}
    )
    assert resp.status_code == 401
    assert resp.json()["code"] == "account_disabled"


async def test_login_rate_limit_per_email(client: ApiClient, make_user: MakeUser) -> None:
    await make_user("target@example.com")
    for _ in range(5):
        resp = await client.post(
            "/api/v1/auth/login", json={"email": "target@example.com", "password": "nope-nope"}
        )
        assert resp.status_code == 401
    resp = await client.post(
        "/api/v1/auth/login", json={"email": "target@example.com", "password": PASSWORD}
    )
    assert resp.status_code == 429
    assert resp.json()["code"] == "too_many_attempts"
    assert int(resp.headers["Retry-After"]) > 0


async def test_login_rate_limit_per_ip(
    client: ApiClient, make_user: MakeUser, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LOGIN_MAX_FAILURES_PER_IP", "3")
    from app.core.config import get_settings

    get_settings.cache_clear()
    await make_user("victim@example.com")
    for i in range(3):
        await client.post(
            "/api/v1/auth/login", json={"email": f"spray{i}@example.com", "password": "x"}
        )
    resp = await client.post(
        "/api/v1/auth/login", json={"email": "victim@example.com", "password": PASSWORD}
    )
    assert resp.status_code == 429
    get_settings.cache_clear()


async def test_invalid_request_body(client: ApiClient) -> None:
    resp = await client.post("/api/v1/auth/login", json={"email": "not-an-email", "password": "x"})
    assert resp.status_code == 422


async def test_me_requires_auth(client: ApiClient) -> None:
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401
    assert resp.json()["code"] == "not_authenticated"


async def test_expired_and_garbage_access_tokens(client: ApiClient, make_user: MakeUser) -> None:
    user = await make_user()
    old = create_token(
        user.id, "access", timedelta(minutes=1), now=datetime.now(UTC) - timedelta(hours=1)
    )
    client.cookies.set(ACCESS_COOKIE, old, path="/api")
    resp = await client.get("/api/v1/auth/me")
    assert resp.json()["code"] == "token_expired"
    client.cookies.set(ACCESS_COOKIE, "garbage", path="/api")
    assert (await client.get("/api/v1/auth/me")).json()["code"] == "token_invalid"


async def test_refresh_rotates_and_detects_reuse(
    client: ApiClient, make_user: MakeUser, session: AsyncSession
) -> None:
    await make_user("r@example.com")
    await client.login("r@example.com")
    first_refresh = client.cookies[REFRESH_COOKIE]

    assert (await client.post("/api/v1/auth/refresh")).status_code == 204
    second_refresh = client.cookies[REFRESH_COOKIE]
    assert second_refresh != first_refresh
    assert (await client.get("/api/v1/auth/me")).status_code == 200

    # Within the grace window, a parallel refresh with the old token is tolerated.
    client.cookies.set(REFRESH_COOKIE, first_refresh, path="/api/v1/auth")
    assert (await client.post("/api/v1/auth/refresh")).status_code == 204

    # After the grace window, replaying a rotated-out token kills the whole session.
    for row in (await session.scalars(select(RefreshToken))).all():
        if row.revoked_at is not None:
            row.revoked_at = row.revoked_at - timedelta(minutes=5)
    await session.commit()
    client.cookies.set(REFRESH_COOKIE, first_refresh, path="/api/v1/auth")
    resp = await client.post("/api/v1/auth/refresh")
    assert resp.status_code == 401
    assert resp.json()["code"] == "token_revoked"
    live = (
        await session.scalars(select(RefreshToken).where(RefreshToken.revoked_at.is_(None)))
    ).all()
    assert live == []


async def test_refresh_without_or_with_bad_token(client: ApiClient) -> None:
    assert (await client.post("/api/v1/auth/refresh")).status_code == 401
    client.cookies.set(REFRESH_COOKIE, "garbage", path="/api/v1/auth")
    assert (await client.post("/api/v1/auth/refresh")).status_code == 401


async def test_deactivated_user_loses_access(make_client: MakeClient, make_user: MakeUser) -> None:
    await make_user("admin@example.com", is_superadmin=True)
    target = await make_user("t@example.com")
    admin, victim = await make_client(), await make_client()
    await admin.login("admin@example.com")
    await victim.login("t@example.com")
    resp = await admin.patch(f"/api/v1/admin/users/{target.id}", json={"is_active": False})
    assert resp.status_code == 200
    assert (await victim.get("/api/v1/auth/me")).status_code == 401
    assert (await victim.post("/api/v1/auth/refresh")).status_code == 401


async def test_update_me(client: ApiClient, make_user: MakeUser) -> None:
    await make_user("me@example.com")
    await client.login("me@example.com")
    resp = await client.patch(
        "/api/v1/auth/me", json={"display_name": " Олена ", "preferred_language": "pl"}
    )
    assert resp.status_code == 200
    assert resp.json()["display_name"] == "Олена"
    assert resp.json()["preferred_language"] == "pl"
    resp = await client.patch("/api/v1/auth/me", json={"preferred_language": "de"})
    assert resp.status_code == 422


async def test_change_password_revokes_other_sessions(
    make_client: MakeClient, make_user: MakeUser
) -> None:
    await make_user("pw@example.com")
    laptop, phone = await make_client(), await make_client()
    await laptop.login("pw@example.com")
    await phone.login("pw@example.com")

    resp = await laptop.post(
        "/api/v1/auth/me/password",
        json={"current_password": "wrong-one", "new_password": "a-new-long-password"},
    )
    assert resp.json()["code"] == "invalid_password"
    resp = await laptop.post(
        "/api/v1/auth/me/password",
        json={"current_password": PASSWORD, "new_password": "short"},
    )
    assert resp.status_code == 422

    # sessions_valid_after has second precision: make sure a new second starts.
    import asyncio

    await asyncio.sleep(1.05)
    resp = await laptop.post(
        "/api/v1/auth/me/password",
        json={"current_password": PASSWORD, "new_password": "a-new-long-password"},
    )
    assert resp.status_code == 204
    assert (await laptop.get("/api/v1/auth/me")).status_code == 200
    assert (await phone.get("/api/v1/auth/me")).status_code == 401
    assert (await phone.post("/api/v1/auth/refresh")).status_code == 401
    await phone.login("pw@example.com", "a-new-long-password")


# --- 2FA --------------------------------------------------------------------------------


async def _enable_2fa(client: ApiClient) -> tuple[str, list[str]]:
    setup = (await client.post("/api/v1/auth/2fa/setup")).json()
    assert setup["qr_svg"].startswith("<svg")
    resp = await client.post("/api/v1/auth/2fa/enable", json={"code": "000000"})
    assert resp.json()["code"] == "invalid_code"
    resp = await client.post("/api/v1/auth/2fa/enable", json={"code": totp_code(setup["secret"])})
    assert resp.status_code == 200
    return setup["secret"], resp.json()["recovery_codes"]


async def test_totp_login_flow(make_client: MakeClient, make_user: MakeUser) -> None:
    await make_user("2fa@example.com")
    c = await make_client()
    await c.login("2fa@example.com")
    secret, codes = await _enable_2fa(c)
    assert (await c.post("/api/v1/auth/2fa/setup")).json()["code"] == "totp_already_enabled"
    assert (await c.get("/api/v1/auth/me")).json()["totp_enabled"] is True

    fresh = await make_client()
    body = await fresh.login("2fa@example.com")
    assert body == {"status": "mfa_required", "user": None}
    assert fresh.cookies.get(MFA_COOKIE)
    assert (await fresh.get("/api/v1/auth/me")).status_code == 401

    resp = await fresh.post("/api/v1/auth/login/mfa", json={"code": "123456"})
    assert resp.status_code == 401
    assert resp.json()["code"] == "invalid_code"
    resp = await fresh.post("/api/v1/auth/login/mfa", json={"code": totp_code(secret, 1)})
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert (await fresh.get("/api/v1/auth/me")).status_code == 200

    # Recovery code works once.
    other = await make_client()
    await other.login("2fa@example.com")
    resp = await other.post("/api/v1/auth/login/mfa", json={"code": codes[0].upper()})
    assert resp.status_code == 200
    again = await make_client()
    await again.login("2fa@example.com")
    resp = await again.post("/api/v1/auth/login/mfa", json={"code": codes[0]})
    assert resp.status_code == 401


async def test_mfa_without_password_step(client: ApiClient) -> None:
    resp = await client.post("/api/v1/auth/login/mfa", json={"code": "123456"})
    assert resp.status_code == 401
    assert resp.json()["code"] == "mfa_session_expired"
    client.cookies.set(MFA_COOKIE, "garbage", path="/api/v1/auth")
    resp = await client.post("/api/v1/auth/login/mfa", json={"code": "123456"})
    assert resp.json()["code"] == "mfa_session_expired"


async def test_totp_disable_and_regenerate(client: ApiClient, make_user: MakeUser) -> None:
    await make_user("d@example.com")
    await client.login("d@example.com")
    assert (await client.post("/api/v1/auth/2fa/enable", json={"code": "123456"})).json()[
        "code"
    ] == "totp_not_set_up"
    secret, codes = await _enable_2fa(client)

    resp = await client.post("/api/v1/auth/2fa/recovery-codes", json={"code": codes[1]})
    assert resp.status_code == 200
    new_codes = resp.json()["recovery_codes"]
    assert set(new_codes).isdisjoint(codes)

    resp = await client.post(
        "/api/v1/auth/2fa/disable", json={"password": "wrong-password", "code": new_codes[0]}
    )
    assert resp.json()["code"] == "invalid_password"
    resp = await client.post(
        "/api/v1/auth/2fa/disable", json={"password": PASSWORD, "code": "999999"}
    )
    assert resp.json()["code"] == "invalid_code"
    resp = await client.post(
        "/api/v1/auth/2fa/disable", json={"password": PASSWORD, "code": totp_code(secret, 1)}
    )
    assert resp.status_code == 204
    assert (await client.get("/api/v1/auth/me")).json()["totp_enabled"] is False
    resp = await client.post(
        "/api/v1/auth/2fa/disable", json={"password": PASSWORD, "code": "123456"}
    )
    assert resp.json()["code"] == "totp_not_enabled"
    resp = await client.post("/api/v1/auth/2fa/recovery-codes", json={"code": "123456"})
    assert resp.json()["code"] == "totp_not_enabled"


# --- Invitations & password reset -------------------------------------------------------


async def test_invitation_flow(
    make_client: MakeClient, make_user: MakeUser, make_tree: Callable[..., Awaitable[Any]]
) -> None:
    admin_user = await make_user("root@example.com", is_superadmin=True)
    tree = await make_tree(admin_user)
    admin = await make_client()
    await admin.login("root@example.com")
    resp = await admin.post(
        "/api/v1/admin/invitations",
        json={"email": "Cousin@Example.com", "tree_id": str(tree.id), "role": "contributor"},
    )
    assert resp.status_code == 201
    url = resp.json()["url"]
    token = url.rsplit("/", 1)[-1]
    assert url.startswith("http://localhost:8080/invite/")

    guest = await make_client()
    info = await guest.get(f"/api/v1/auth/invitations/{token}")
    assert info.json()["email"] == "cousin@example.com"
    assert info.json()["tree_name"] == tree.name

    resp = await guest.post(
        f"/api/v1/auth/invitations/{token}/accept",
        json={"display_name": "Cousin", "password": "x"},
    )
    assert resp.status_code == 422
    resp = await guest.post(
        f"/api/v1/auth/invitations/{token}/accept",
        json={
            "display_name": "Cousin",
            "password": "long-enough-password",
            "preferred_language": "en",
        },
    )
    assert resp.status_code == 200
    me = resp.json()["user"]
    assert me["trees"] == [{"id": str(tree.id), "name": tree.name, "role": "contributor"}]
    assert me["preferred_language"] == "en"

    # One-time use.
    assert (await guest.get(f"/api/v1/auth/invitations/{token}")).status_code == 404
    assert (await guest.get("/api/v1/auth/invitations/unknown-token")).json()[
        "code"
    ] == "link_invalid"


async def test_password_reset_flow(make_client: MakeClient, make_user: MakeUser) -> None:
    await make_user("root@example.com", is_superadmin=True)
    target = await make_user("forgot@example.com")
    admin = await make_client()
    await admin.login("root@example.com")
    first = (await admin.post(f"/api/v1/admin/users/{target.id}/password-reset")).json()["url"]
    second = (await admin.post(f"/api/v1/admin/users/{target.id}/password-reset")).json()["url"]
    old_token, token = first.rsplit("/", 1)[-1], second.rsplit("/", 1)[-1]

    guest = await make_client()
    assert (await guest.get(f"/api/v1/auth/password-reset/{old_token}")).status_code == 404
    info = await guest.get(f"/api/v1/auth/password-reset/{token}")
    assert info.json()["email"] == "forgot@example.com"
    resp = await guest.post(
        f"/api/v1/auth/password-reset/{token}", json={"password": "brand-new-password"}
    )
    assert resp.status_code == 204
    await guest.login("forgot@example.com", "brand-new-password")
    resp = await guest.post(
        f"/api/v1/auth/password-reset/{token}", json={"password": "another-password"}
    )
    assert resp.status_code == 404


async def test_purge_expired_auth_records(session: AsyncSession, make_user: MakeUser) -> None:
    import uuid

    from app.core.security import utcnow
    from app.models import LoginAttempt
    from app.services.auth import purge_expired

    user = await make_user()
    now = utcnow()
    session.add_all(
        [
            LoginAttempt(
                email="old@example.com", success=False, created_at=now - timedelta(days=40)
            ),
            LoginAttempt(email="new@example.com", success=False, created_at=now),
            RefreshToken(
                user_id=user.id, family_id=uuid.uuid4(), expires_at=now - timedelta(days=10)
            ),
            RefreshToken(
                user_id=user.id, family_id=uuid.uuid4(), expires_at=now + timedelta(days=1)
            ),
        ]
    )
    await session.commit()
    assert await purge_expired(session) == (1, 1)
