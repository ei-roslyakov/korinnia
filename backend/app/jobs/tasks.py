"""Background tasks.

Queues:
- default: short jobs
- media:   thumbnails / previews (phase 6)
- maintenance: integrity checks, backups (phase 9)
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from app.jobs.app import app

logger = logging.getLogger(__name__)


@app.task(name="system.ping", queue="default")
async def ping(message: str = "pong") -> str:
    """Smoke-test task: proves the worker consumes jobs from PostgreSQL."""
    logger.info("ping task executed", extra={"message_text": message})
    return message


@app.periodic(cron="*/15 * * * *")
@app.task(name="system.heartbeat", queue="maintenance", queueing_lock="system.heartbeat")
async def heartbeat(timestamp: int) -> None:
    """Periodic heartbeat so the worker's liveness is visible in logs and the jobs table."""
    logger.info(
        "worker heartbeat",
        extra={"scheduled_at": datetime.fromtimestamp(timestamp, tz=UTC).isoformat()},
    )
