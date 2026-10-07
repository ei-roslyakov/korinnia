"""Background tasks.

Queues:
- default: short jobs
- media:   thumbnails / previews (phase 6)
- maintenance: integrity checks, backups (phase 9)
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from app.core.db import get_sessionmaker
from app.jobs.app import app
from app.services.auth import purge_expired

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


@app.periodic(cron="17 3 * * *")
@app.task(name="auth.purge_expired", queue="maintenance", queueing_lock="auth.purge_expired")
async def purge_expired_auth_records(timestamp: int) -> None:
    """Daily: drop old login attempts (throttling data) and long-expired refresh tokens."""
    async with get_sessionmaker()() as session:
        attempts, tokens = await purge_expired(session)
    logger.info(
        "purged expired auth records",
        extra={"login_attempts": attempts, "refresh_tokens": tokens},
    )
