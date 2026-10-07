"""Test fixtures.

Tests that touch the database use a real PostgreSQL (database name must end in `_test`).
The schema is migrated once per session; every test runs inside an outer transaction that
is rolled back afterwards, so service-level `commit()` calls only release savepoints.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession, create_async_engine

os.environ["ENVIRONMENT"] = "test"
os.environ.setdefault("POSTGRES_DB", "korinnia_test")
os.environ["COOKIE_SECURE"] = "false"  # the test client talks plain http://
os.environ["MEDIA_X_ACCEL"] = "false"  # no nginx in tests: the backend serves files
os.environ.setdefault("SECRET_KEY", "test-secret-key-test-secret-key-0123456789")

from alembic import command
from alembic.config import Config

from app.api.cookies import CSRF_COOKIE
from app.core.config import get_settings
from app.core.db import get_session
from app.main import create_app
from app.models import Tree, TreeMembership, TreeRole, User
from app.services import trees as tree_service
from app.services import users as user_service
from app.services.context import Actor
from app.storage import LocalStorage, get_storage
from tests.helpers import Ctx

BACKEND_DIR = Path(__file__).resolve().parent.parent
PASSWORD = "correct-horse-battery"

get_settings.cache_clear()


# --- Database ---------------------------------------------------------------------------


def _database_available() -> str | None:
    """Return None if the test DB is reachable, else the reason."""
    settings = get_settings()
    if not settings.postgres_db.endswith("_test") and not (
        settings.database_url_override or ""
    ).endswith("_test"):
        return f"database {settings.postgres_db!r} is not a *_test database"

    async def _ping() -> None:
        engine = create_async_engine(settings.database_url)
        try:
            async with engine.connect():
                pass
        finally:
            await engine.dispose()

    try:
        asyncio.run(_ping())
    except Exception as exc:
        return f"PostgreSQL not reachable: {exc.__class__.__name__}"
    return None


@pytest.fixture(scope="session")
def migrated_db() -> str:
    reason = _database_available()
    if reason:
        pytest.skip(reason)
    command.upgrade(Config(str(BACKEND_DIR / "alembic.ini")), "head")
    return get_settings().database_url


@pytest.fixture(scope="session")
async def engine(migrated_db: str) -> AsyncIterator[Any]:
    eng = create_async_engine(migrated_db)
    yield eng
    await eng.dispose()


@pytest.fixture
async def connection(engine: Any) -> AsyncIterator[AsyncConnection]:
    async with engine.connect() as conn:
        trans = await conn.begin()
        try:
            yield conn
        finally:
            await trans.rollback()


@pytest.fixture
async def session(connection: AsyncConnection) -> AsyncIterator[AsyncSession]:
    s = AsyncSession(
        bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
    )
    try:
        yield s
    finally:
        await s.close()


# --- App & clients ----------------------------------------------------------------------


@pytest.fixture
def local_storage(tmp_path: Path) -> LocalStorage:
    return LocalStorage(tmp_path / "media")


@pytest.fixture
def app(local_storage: LocalStorage, request: pytest.FixtureRequest) -> Iterator[Any]:
    get_settings.cache_clear()
    application = create_app()
    application.dependency_overrides[get_storage] = lambda: local_storage
    if "session" in request.fixturenames:
        db_session: AsyncSession = request.getfixturevalue("session")

        async def _session() -> AsyncIterator[AsyncSession]:
            yield db_session

        application.dependency_overrides[get_session] = _session
    yield application
    application.dependency_overrides.clear()


class ApiClient(AsyncClient):
    """httpx client that behaves like the frontend: keeps cookies, echoes the CSRF token."""

    async def prime_csrf(self) -> None:
        await self.get("/api/v1/auth/csrf")
        self.headers["X-CSRF-Token"] = self.cookies[CSRF_COOKIE]

    async def login(self, email: str, password: str = PASSWORD) -> dict[str, Any]:
        resp = await self.post("/api/v1/auth/login", json={"email": email, "password": password})
        assert resp.status_code == 200, resp.text
        return resp.json()  # type: ignore[no-any-return]


@pytest.fixture
def make_client(app: Any) -> Callable[[], Awaitable[ApiClient]]:
    clients: list[ApiClient] = []

    async def _make() -> ApiClient:
        c = ApiClient(transport=ASGITransport(app=app), base_url="http://test")
        await c.prime_csrf()
        clients.append(c)
        return c

    return _make


@pytest.fixture
async def client(make_client: Callable[[], Awaitable[ApiClient]]) -> ApiClient:
    return await make_client()


# --- Data factories ---------------------------------------------------------------------

SYSTEM = Actor(None, ip="test")


@pytest.fixture
def make_user(session: AsyncSession) -> Callable[..., Awaitable[User]]:
    counter = 0

    async def _make(
        email: str | None = None,
        *,
        password: str = PASSWORD,
        is_superadmin: bool = False,
        is_active: bool = True,
        name: str | None = None,
    ) -> User:
        nonlocal counter
        counter += 1
        user = await user_service.create_user(
            session,
            email=email or f"user{counter}@example.com",
            display_name=name or f"User {counter}",
            password=password,
            is_superadmin=is_superadmin,
            actor=SYSTEM,
        )
        if not is_active:
            user.is_active = False
            await session.commit()
        return user

    return _make


@pytest.fixture
def make_tree(session: AsyncSession) -> Callable[..., Awaitable[Tree]]:
    async def _make(owner: User, name: str = "Rosliakov family") -> Tree:
        return await tree_service.create_tree(
            session, name=name, description=None, owner=owner, actor=SYSTEM
        )

    return _make


@pytest.fixture
def add_member(session: AsyncSession) -> Callable[..., Awaitable[TreeMembership]]:
    async def _add(tree: Tree, user: User, role: TreeRole) -> TreeMembership:
        membership = TreeMembership(tree_id=tree.id, user_id=user.id, role=role)
        session.add(membership)
        await session.commit()
        return membership

    return _add


@pytest.fixture
async def ctx(
    make_user: Callable[..., Awaitable[User]],
    make_tree: Callable[..., Awaitable[Tree]],
    make_client: Callable[[], Awaitable[ApiClient]],
) -> Ctx:
    owner = await make_user("owner@example.com")
    tree = await make_tree(owner)
    client = await make_client()
    await client.login("owner@example.com")
    return Ctx(tree=tree, editor=client, base=f"/api/v1/trees/{tree.id}")


@pytest.fixture(autouse=True)
def job_queue() -> Iterator[Any]:
    """Jobs are recorded in memory instead of PostgreSQL (assert on `.jobs`)."""
    from procrastinate import testing

    from app.jobs.app import app as procrastinate_app

    connector = testing.InMemoryConnector()
    with procrastinate_app.replace_connector(connector):
        yield connector
