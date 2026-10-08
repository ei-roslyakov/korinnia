"""Integrity checks of stored originals (phase 9)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import IntegrityRun, MediaFile
from app.storage import LocalStorage
from tests.helpers import Ctx
from tests.test_media_api import jpeg, png, upload


async def _superadmin(ctx: Ctx, make_user: Any, make_client: Any) -> Any:
    await make_user("root@example.com", is_superadmin=True)
    c = await make_client()
    await c.login("root@example.com")
    return c


async def test_integrity_check_finds_missing_changed_and_untracked_files(
    ctx: Ctx,
    session: AsyncSession,
    local_storage: LocalStorage,
    make_user: Any,
    make_client: Any,
    monkeypatch: pytest.MonkeyPatch,
    job_queue: Any,
) -> None:
    from app.jobs import tasks

    @asynccontextmanager
    async def factory() -> Any:
        yield session

    monkeypatch.setattr(tasks, "get_sessionmaker", lambda: factory)
    monkeypatch.setattr(tasks, "get_storage", lambda: local_storage)

    good = (await upload(ctx, "good.jpg", jpeg())).json()
    changed = (await upload(ctx, "changed.png", png())).json()
    gone = (await upload(ctx, "gone.jpg", jpeg(width=70))).json()
    rows = {str(m.id): m for m in await session.scalars(select(MediaFile))}
    # Bit rot (same size, different bytes), a lost file and a stray file nobody owns.
    path = local_storage.path(rows[changed["id"]].original_key)
    data = bytearray(path.read_bytes())
    data[-1] ^= 0xFF
    path.write_bytes(bytes(data))
    local_storage.path(rows[gone["id"]].original_key).unlink()
    stray = local_storage.path("originals/stray/file.bin")
    stray.parent.mkdir(parents=True)
    stray.write_bytes(b"x")

    sa = await _superadmin(ctx, make_user, make_client)
    job_queue.jobs.clear()  # the uploads queued media processing
    resp = await sa.post("/api/v1/admin/integrity/run")
    assert resp.status_code == 202
    run_id = resp.json()["id"]
    assert [j["args"] for j in job_queue.jobs.values()] == [{"run_id": run_id}]
    # A second run cannot start while one is running.
    assert (await sa.post("/api/v1/admin/integrity/run")).json()["code"] == (
        "integrity_check_running"
    )

    await tasks.check_integrity(run_id=run_id)
    overview = (await sa.get("/api/v1/admin/integrity")).json()
    run = overview["runs"][0]
    assert (run["status"], run["files_checked"], run["problems"], run["untracked_files"]) == (
        "done",
        3,
        2,
        1,
    )
    assert run["triggered_by"] is not None
    assert overview["total_files"] == 3
    problems = {i["filename"]: i["problem"] for i in overview["issues"]}
    assert problems == {"changed.png": "hash_mismatch", "gone.jpg": "missing"}
    assert good["id"] not in {i["media_id"] for i in overview["issues"]}
    assert all(i["tree_name"] == ctx.tree.name for i in overview["issues"])


async def test_weekly_check_and_access(
    ctx: Ctx,
    session: AsyncSession,
    local_storage: LocalStorage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.jobs import tasks

    @asynccontextmanager
    async def factory() -> Any:
        yield session

    monkeypatch.setattr(tasks, "get_sessionmaker", lambda: factory)
    monkeypatch.setattr(tasks, "get_storage", lambda: local_storage)
    await upload(ctx, "a.jpg", jpeg())
    await tasks.weekly_integrity_check(timestamp=0)
    run = (await session.scalars(select(IntegrityRun))).one()
    assert (run.trigger, run.status, run.problems, run.triggered_by_id) == (
        "scheduled",
        "done",
        0,
        None,
    )
    # Tree owners are not superadmins.
    assert (await ctx.editor.get("/api/v1/admin/integrity")).status_code == 403
    assert (await ctx.editor.post("/api/v1/admin/integrity/run")).status_code == 403
