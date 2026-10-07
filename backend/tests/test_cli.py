from __future__ import annotations

import io
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import cli
from app.core.config import Settings
from app.core.errors import AppError
from app.core.security import verify_password
from app.models import User
from app.services.users import bootstrap_superadmin


def _settings(**kw: Any) -> Settings:
    return Settings(_env_file=None, **kw)


async def test_bootstrap_creates_once(session: AsyncSession) -> None:
    s = _settings(
        superadmin_email="Boss@Example.com", superadmin_password=SecretStr("long-password-1")
    )
    user = await bootstrap_superadmin(session, s)
    assert user is not None
    assert user.email == "boss@example.com"
    assert user.is_superadmin
    assert verify_password("long-password-1", user.password_hash)
    assert await bootstrap_superadmin(session, s) is None  # idempotent


async def test_bootstrap_noop_without_env(session: AsyncSession) -> None:
    s = _settings(superadmin_email=None, superadmin_password=None)
    assert await bootstrap_superadmin(session, s) is None


async def test_bootstrap_rejects_short_password(session: AsyncSession) -> None:
    s = _settings(superadmin_email="a@example.com", superadmin_password=SecretStr("short"))
    with pytest.raises(AppError, match="superadmin_password_too_short"):
        await bootstrap_superadmin(session, s)


async def test_bootstrap_promotes_existing_user(session: AsyncSession, make_user: Any) -> None:
    existing = await make_user("me@example.com", is_active=False)
    s = _settings(
        superadmin_email="me@example.com", superadmin_password=SecretStr("long-password-1")
    )
    user = await bootstrap_superadmin(session, s)
    assert user is not None
    assert user.id == existing.id
    assert user.is_superadmin
    assert user.is_active


@pytest.fixture
def cli_session(session: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> AsyncSession:
    @asynccontextmanager
    async def _factory() -> AsyncIterator[AsyncSession]:
        yield session

    monkeypatch.setattr(cli, "get_sessionmaker", lambda: _factory)
    engine = MagicMock()
    engine.dispose = AsyncMock()
    monkeypatch.setattr(cli, "get_engine", lambda: engine)
    monkeypatch.setattr(cli, "configure_logging", lambda level: None)
    return session


async def _run(argv: list[str]) -> int:
    return await cli.run(cli.parse_args(argv))


def test_main_wires_parse_and_run(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []

    async def fake_run(args: Any) -> int:
        seen.append(args.command)
        return 0

    monkeypatch.setattr(cli, "run", fake_run)
    monkeypatch.setattr(cli, "configure_logging", lambda level: None)
    assert cli.main(["bootstrap"]) == 0
    assert seen == ["bootstrap"]


async def test_cli_commands(
    cli_session: AsyncSession,
    make_user: Any,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("long-password-1\n"))
    assert await _run(["create-superadmin", "cli@example.com", "CLI Admin"]) == 0
    user = (await cli_session.scalars(select(User).where(User.email == "cli@example.com"))).one()
    assert user.is_superadmin

    assert await _run(["reset-link", "cli@example.com"]) == 0
    assert "/reset-password/" in capsys.readouterr().out
    assert await _run(["disable-2fa", "cli@example.com"]) == 0
    assert await _run(["reset-link", "missing@example.com"]) == 1
    assert await _run(["bootstrap"]) == 0
    assert "nothing to do" in capsys.readouterr().out

    monkeypatch.setattr("sys.stdin", io.StringIO("short\n"))
    with pytest.raises(SystemExit):
        await _run(["create-superadmin", "x@example.com", "X"])
    monkeypatch.setattr("sys.stdin", io.StringIO("long-password-1\n"))
    assert await _run(["create-superadmin", "cli@example.com", "Dup"]) == 1  # email_taken
