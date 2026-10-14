"""Session timeouts and the public demo login (one throwaway account per sign-in)."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable, Iterator
from datetime import datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import create_token, decode_token, utcnow
from app.models import RefreshToken, Tree, User
from app.services import demo_sessions
from app.storage import LocalStorage
from tests.conftest import ApiClient

MakeUser = Callable[..., Awaitable[User]]
MakeClient = Callable[[], Awaitable[ApiClient]]

DEMO = {"email": "demo@example.com", "password": "demo@example.com"}


@pytest.fixture
def demo_enabled(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("DEMO_LOGIN_ENABLED", "true")
    get_settings.cache_clear()
    yield
    monkeypatch.undo()
    get_settings.cache_clear()


async def _end_session(session: AsyncSession, user_id: Any) -> None:
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id)
        .values(session_expires_at=utcnow() - timedelta(seconds=1))
    )
    await session.commit()


def test_access_token_never_outlives_the_session() -> None:
    now = utcnow().replace(microsecond=0)
    end = now + timedelta(minutes=5)
    token = create_token(uuid.uuid4(), "access", timedelta(minutes=15), session_expires_at=end)
    payload = decode_token(token, "access")
    assert payload.exp == end
    assert payload.sx == end


async def test_session_ends_and_can_be_extended_before(
    make_user: MakeUser, make_client: MakeClient, session: AsyncSession
) -> None:
    user = await make_user("s@example.com")
    c = await make_client()
    body = await c.login("s@example.com")
    end = body["user"]["session_expires_at"]
    assert end is not None
    me = (await c.get("/api/v1/auth/me")).json()
    assert me["session_expires_at"] == end
    assert me["is_sandbox"] is False

    # Extending moves the end to a full timeout from now.
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id)
        .values(session_expires_at=utcnow() + timedelta(minutes=1))
    )
    await session.commit()
    resp = await c.post("/api/v1/auth/session/extend")
    assert resp.status_code == 200
    left = datetime.fromisoformat(resp.json()["session_expires_at"]) - utcnow()
    assert left > timedelta(hours=7)  # back to the full 8 hours, not the 1 minute left

    # After the end, refreshing and extending fail; the user signs in again.
    await _end_session(session, user.id)
    resp = await c.post("/api/v1/auth/refresh")
    assert resp.status_code == 401
    assert resp.json()["code"] == "session_expired"
    assert (await c.post("/api/v1/auth/session/extend")).status_code == 401
    assert (await c.login("s@example.com"))["status"] == "ok"


async def test_old_sessions_get_a_timeout_at_refresh(
    make_user: MakeUser, make_client: MakeClient, session: AsyncSession
) -> None:
    user = await make_user("old@example.com")
    c = await make_client()
    await c.login("old@example.com")
    await session.execute(
        update(RefreshToken).where(RefreshToken.user_id == user.id).values(session_expires_at=None)
    )
    await session.commit()
    assert (await c.post("/api/v1/auth/refresh")).status_code == 204
    me = (await c.get("/api/v1/auth/me")).json()
    assert me["session_expires_at"] is not None


async def test_demo_login_can_be_off(
    make_client: MakeClient, session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEMO_LOGIN_ENABLED", "false")
    get_settings.cache_clear()
    c = await make_client()
    assert (await c.post("/api/v1/auth/login", json=DEMO)).status_code == 401
    assert (await c.post("/api/v1/auth/demo")).status_code == 404
    get_settings.cache_clear()


async def test_each_demo_sign_in_gets_its_own_family(
    demo_enabled: None,
    make_client: MakeClient,
    make_user: MakeUser,
    session: AsyncSession,
    local_storage: LocalStorage,
) -> None:
    first = await make_client()
    resp = await first.post("/api/v1/auth/login", json=DEMO)
    assert resp.status_code == 200, resp.text
    me = resp.json()["user"]
    assert me["is_sandbox"] is True
    assert me["email"] != "demo@example.com"
    end = me["session_expires_at"]
    trees = (await first.get("/api/v1/trees")).json()
    assert len(trees) == 1
    assert trees[0]["my_role"] == "admin"
    tree_id = trees[0]["id"]
    assert any(local_storage.root.joinpath("originals", tree_id).iterdir())

    # A change by the first visitor…
    resp = await first.patch(f"/api/v1/trees/{tree_id}", json={"name": "Changed by visitor 1"})
    assert resp.status_code == 200
    # …is not seen by the second one, who gets a fresh copy.
    second = await make_client()
    resp = await second.post("/api/v1/auth/demo")
    assert resp.status_code == 200
    assert resp.json()["user"]["id"] != me["id"]
    other = (await second.get("/api/v1/trees")).json()
    assert len(other) == 1
    assert other[0]["id"] != tree_id
    assert other[0]["name"] != "Changed by visitor 1"

    # Demo sessions last 30 minutes and cannot be extended.
    left = datetime.fromisoformat(end) - utcnow()
    assert timedelta(minutes=29) < left <= timedelta(minutes=30)
    resp = await first.post("/api/v1/auth/session/extend")
    assert resp.status_code == 403
    assert resp.json()["code"] == "demo_session_fixed"

    # Nothing that reaches other people or outlives the demo.
    await make_user("real@example.com")
    resp = await first.post(
        f"/api/v1/trees/{tree_id}/members",
        json={"email": "real@example.com", "role": "viewer", "invite": False},
    )
    assert resp.json()["code"] == "not_in_demo"
    resp = await first.post(f"/api/v1/trees/{tree_id}/share-links", json={})
    assert resp.json()["code"] == "not_in_demo"
    assert (await first.post("/api/v1/auth/2fa/setup")).json()["code"] == "not_in_demo"

    # Hidden from the admin panel.
    admin = await make_user("root@example.com", is_superadmin=True)
    ac = await make_client()
    await ac.login(admin.email)
    users = (await ac.get("/api/v1/admin/users")).json()["items"]
    assert all(not u["email"].endswith("sandbox.invalid") for u in users)
    admin_trees = (await ac.get("/api/v1/admin/trees")).json()["items"]
    assert tree_id not in [t["id"] for t in admin_trees]

    # When the session has ended, the account and everything in it are deleted.
    await _end_session(session, me["id"])
    await session.execute(
        update(User)
        .where(User.is_sandbox.is_(True))
        .values(created_at=utcnow() - timedelta(hours=1))
    )
    await session.commit()
    assert await demo_sessions.purge_ended(session, local_storage) == 1
    assert await session.get(Tree, tree_id) is None
    assert not local_storage.root.joinpath("originals", tree_id).exists()
    assert (
        await session.scalar(select(func.count()).select_from(User).where(User.is_sandbox))
    ) == 1  # the second visitor's session is still running
    assert (await first.get("/api/v1/auth/me")).status_code == 401


async def test_demo_sign_ins_are_limited_per_ip(
    demo_enabled: None,
    make_client: MakeClient,
    session: AsyncSession,  # keeps the demo accounts inside the test's transaction
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEMO_LOGINS_PER_IP_PER_HOUR", "1")
    get_settings.cache_clear()
    c = await make_client()
    assert (await c.post("/api/v1/auth/demo")).status_code == 200
    resp = await c.post("/api/v1/auth/demo")
    assert resp.status_code == 429
