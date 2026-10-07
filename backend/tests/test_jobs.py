from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import AsyncMock, patch

import pytest
from procrastinate import testing

from app.jobs import worker
from app.jobs.app import app as procrastinate_app
from app.jobs.tasks import heartbeat, ping


@pytest.fixture
def in_memory_app() -> Iterator[testing.InMemoryConnector]:
    connector = testing.InMemoryConnector()
    with procrastinate_app.replace_connector(connector):
        yield connector


async def test_ping_job_runs(in_memory_app: testing.InMemoryConnector) -> None:
    await ping.defer_async(message="hello")
    await procrastinate_app.run_worker_async(wait=False)
    jobs = [j for j in in_memory_app.jobs.values() if j["task_name"] == "system.ping"]
    assert len(jobs) == 1
    assert jobs[0]["status"] == "succeeded"
    assert jobs[0]["queue_name"] == "default"


async def test_heartbeat_runs() -> None:
    await heartbeat(timestamp=0)


async def test_worker_main_listens_on_all_queues(
    in_memory_app: testing.InMemoryConnector, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("WORKER_CONCURRENCY", "3")
    with patch.object(procrastinate_app, "run_worker_async", new=AsyncMock()) as run:
        await worker.main()
    run.assert_awaited_once_with(
        queues=["default", "media", "maintenance"], concurrency=3, install_signal_handlers=True
    )
