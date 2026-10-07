"""Integration tests against a real PostgreSQL (skipped when unreachable).

Run inside the stack:  make test
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

from app.core.config import get_settings
from app.core.db import get_engine, get_session, ping_database

pytestmark = pytest.mark.db

BACKEND_DIR = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module", autouse=True)
def _require_database() -> None:
    # These tests drop and recreate the schema: never run them against a real database.
    db_name = get_settings().database_url.rsplit("/", 1)[-1]
    if not db_name.endswith("_test"):
        pytest.skip(f"refusing to run destructive DB tests against {db_name!r} (needs *_test)")
    try:
        asyncio.run(ping_database())
    except Exception as exc:  # pragma: no cover - depends on environment
        pytest.skip(f"PostgreSQL not reachable: {exc}")
    finally:
        get_engine.cache_clear()


def _alembic(*args: str) -> None:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    getattr(command, args[0])(cfg, *args[1:])


def _tables() -> set[str]:
    async def _q() -> set[str]:
        engine = get_engine()
        try:
            async with engine.connect() as conn:
                rows = await conn.execute(
                    text("SELECT tablename FROM pg_tables WHERE schemaname = current_schema()")
                )
                return {r[0] for r in rows}
        finally:
            await engine.dispose()
            get_engine.cache_clear()

    return asyncio.run(_q())


def test_migrations_upgrade_downgrade_roundtrip() -> None:
    # Run in a thread-free sync context: alembic's env.py starts its own event loop.
    _alembic("upgrade", "head")
    assert {"procrastinate_jobs", "alembic_version", "users", "trees"} <= _tables()
    _alembic("downgrade", "base")
    assert "procrastinate_jobs" not in _tables()
    _alembic("upgrade", "head")
    assert "procrastinate_jobs" in _tables()


async def test_session_dependency_and_readyz() -> None:
    async for session in get_session():
        assert (await session.execute(text("SELECT 1"))).scalar_one() == 1
    await ping_database()
    await get_engine().dispose()
    get_engine.cache_clear()
