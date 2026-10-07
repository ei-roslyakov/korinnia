"""Worker entrypoint: `python -m app.jobs.worker` (JSON logging + procrastinate worker)."""

from __future__ import annotations

import asyncio
import os

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.jobs.app import app

QUEUES = ["default", "media", "maintenance"]


async def main() -> None:
    configure_logging(get_settings().log_level)
    concurrency = int(os.environ.get("WORKER_CONCURRENCY", "2"))
    async with app.open_async():
        await app.run_worker_async(
            queues=QUEUES, concurrency=concurrency, install_signal_handlers=True
        )


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(main())
