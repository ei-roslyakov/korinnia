"""Background tasks.

Queues:
- default: short jobs
- media:   thumbnails / previews (phase 6)
- maintenance: integrity checks, backups (phase 9)
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.db import get_sessionmaker
from app.core.security import utcnow
from app.jobs.app import app
from app.models import MediaFile, ProcessingStatus
from app.services.auth import purge_expired
from app.services.genealogy import media as media_service
from app.storage import get_storage

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


@app.task(name="media.process", queue="media", retry=2)
async def process_media_file(media_id: str) -> None:
    """Generate thumbnails / web versions for an uploaded file."""
    async with get_sessionmaker()() as session:
        await media_service.process_media(session, get_storage(), uuid.UUID(media_id))


@app.task(name="media.avatar", queue="media", retry=2)
async def make_person_avatar(person_id: str) -> None:
    """Render a person's portrait (crop of the primary photo)."""
    async with get_sessionmaker()() as session:
        await media_service.make_avatar(session, get_storage(), uuid.UUID(person_id))


@app.periodic(cron="*/30 * * * *")
@app.task(name="media.requeue_stuck", queue="maintenance", queueing_lock="media.requeue_stuck")
async def requeue_stuck_media(timestamp: int) -> None:
    """Re-queue items still 'pending' 15 minutes after upload (e.g. enqueue failed)."""
    from app.jobs.queue import enqueue_media_processing

    async with get_sessionmaker()() as session:
        stuck = list(
            await session.scalars(
                select(MediaFile.id).where(
                    MediaFile.processing_status == ProcessingStatus.pending,
                    MediaFile.deleted_at.is_(None),
                    MediaFile.created_at < utcnow() - timedelta(minutes=15),
                )
            )
        )
    for media_id in stuck:
        await enqueue_media_processing(media_id)
    if stuck:
        logger.info("re-queued stuck media", extra={"count": len(stuck)})
