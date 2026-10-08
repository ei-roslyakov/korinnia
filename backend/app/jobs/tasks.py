"""Background tasks.

Queues:
- default: short jobs
- media:   thumbnails / previews (phase 6)
- maintenance: periodic housekeeping and integrity checks of stored originals
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.db import get_sessionmaker
from app.core.security import utcnow
from app.jobs.app import app
from app.models import MediaFile, ProcessingStatus, User
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


@app.task(name="demo.create_for_user", queue="default", retry=2)
async def create_demo_tree(user_id: str) -> None:
    """Give a (new) user their own copy of the demo family."""
    from app import seed as demo  # the demo data imports most services; load lazily

    async with get_sessionmaker()() as session:
        user = await session.get(User, uuid.UUID(user_id))
        if user is None or not user.is_active:
            return
        tree = await demo.seed(session, user, storage=get_storage())
    if tree is not None:
        logger.info("demo tree created", extra={"user_id": user_id, "tree_id": str(tree.id)})


# --- Integrity of stored originals (phase 9) --------------------------------------------


@app.task(name="integrity.check", queue="maintenance", lock="integrity")
async def check_integrity(run_id: str) -> None:
    """Re-hash every stored original for an integrity run created by `start_run`."""
    from app.services import integrity

    async with get_sessionmaker()() as session:
        await integrity.run_check(session, get_storage(), uuid.UUID(run_id))


@app.periodic(cron="23 4 * * 0")
@app.task(name="integrity.weekly", queue="maintenance", queueing_lock="integrity.weekly")
async def weekly_integrity_check(timestamp: int) -> None:
    """Sundays 04:23: a full integrity check (skipped if one is already running)."""
    from app.core.errors import ConflictError
    from app.services import integrity
    from app.services.context import Actor

    async with get_sessionmaker()() as session:
        try:
            run = await integrity.start_run(session, trigger="scheduled", actor=Actor(None))
        except ConflictError:
            logger.info("integrity check already running; weekly run skipped")
            return
        await integrity.run_check(session, get_storage(), run.id)


# --- GEDCOM import (phase 9) --------------------------------------------------------------


@app.task(name="gedcom.analyze", queue="default", lock="gedcom")
async def analyze_gedcom(import_id: str) -> None:
    """Read an uploaded GEDCOM file and build its preview."""
    from app.services import gedcom_import

    async with get_sessionmaker()() as session:
        await gedcom_import.analyze(session, get_storage(), uuid.UUID(import_id))


@app.task(name="gedcom.apply", queue="default", lock="gedcom")
async def apply_gedcom(import_id: str) -> None:
    """Import a confirmed GEDCOM file into its tree (one transaction)."""
    from app.services import gedcom_import

    async with get_sessionmaker()() as session:
        await gedcom_import.apply(session, get_storage(), uuid.UUID(import_id))


@app.task(name="gedcom.undo", queue="default", lock="gedcom")
async def undo_gedcom(import_id: str) -> None:
    """Move what an import created to the trash."""
    from app.services import gedcom_import

    async with get_sessionmaker()() as session:
        await gedcom_import.undo(session, uuid.UUID(import_id))
