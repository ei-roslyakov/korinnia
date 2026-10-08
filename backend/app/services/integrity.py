"""Integrity checks of stored originals (phase 9).

Every original was hashed (SHA-256) when it was written; a check reads each one back and
compares size and hash with what the database recorded. Files that are missing, a different
size, a different hash or unreadable are recorded as issues of the run. Derived files
(web versions, thumbnails, portraits) are not checked: they can be regenerated.

Soft-deleted media are checked too: their originals are kept until permanent deletion.
"""

from __future__ import annotations

import logging
import uuid
from datetime import timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import IntegrityProblem, IntegrityStatus
from app.core.errors import ConflictError, NotFoundError
from app.core.security import utcnow
from app.models import IntegrityIssue, IntegrityRun, MediaFile, User
from app.services import audit
from app.services.context import Actor
from app.storage import ObjectNotFoundError, Storage

logger = logging.getLogger(__name__)

ORIGINALS_PREFIX = "originals/"
PAGE = 200
# A run still "running" after this long was interrupted (worker restart); a new one may start.
STALE_AFTER = timedelta(hours=12)


async def _close_stale(session: AsyncSession) -> None:
    await session.execute(
        update(IntegrityRun)
        .where(
            IntegrityRun.status == IntegrityStatus.running,
            IntegrityRun.started_at < utcnow() - STALE_AFTER,
        )
        .values(status=IntegrityStatus.failed, finished_at=utcnow(), error="interrupted")
    )


async def start_run(session: AsyncSession, *, trigger: str, actor: Actor) -> IntegrityRun:
    """Create a run record (the worker fills it in). Only one run at a time."""
    await _close_stale(session)
    running = await session.scalar(
        select(IntegrityRun.id).where(IntegrityRun.status == IntegrityStatus.running)
    )
    if running:
        raise ConflictError("integrity_check_running")
    run = IntegrityRun(
        id=uuid.uuid4(),
        trigger=trigger,
        triggered_by_id=actor.user.id if actor.user else None,
        status=IntegrityStatus.running,
        files_checked=0,
        bytes_checked=0,
        problems=0,
        untracked_files=0,
    )
    session.add(run)
    if actor.user:
        audit.record(session, actor, "integrity.start", "integrity_run", run.id)
    await session.commit()
    return run


async def _check_file(
    storage: Storage, media: MediaFile
) -> tuple[IntegrityProblem | None, int | None, str | None]:
    """(problem, actual size, actual hash) of one original."""
    try:
        size = await storage.size(media.original_key)
        if size != media.size:
            return IntegrityProblem.size_mismatch, size, None
        digest = await storage.sha256(media.original_key)
    except ObjectNotFoundError:
        return IntegrityProblem.missing, None, None
    except OSError:  # permissions, I/O errors on a failing disk, …
        return IntegrityProblem.unreadable, None, None
    if digest != media.sha256:
        return IntegrityProblem.hash_mismatch, size, digest
    return None, size, digest


async def run_check(session: AsyncSession, storage: Storage, run_id: uuid.UUID) -> IntegrityRun:
    """Check every original; progress is committed page by page so the UI can follow it."""
    run = await session.get(IntegrityRun, run_id)
    if run is None:
        raise NotFoundError("integrity_run_not_found")
    known: set[str] = set()
    last_id: uuid.UUID | None = None
    try:
        while True:
            query = select(MediaFile).order_by(MediaFile.id).limit(PAGE)
            if last_id is not None:
                query = query.where(MediaFile.id > last_id)
            page = list(await session.scalars(query))
            if not page:
                break
            for media in page:
                known.add(media.original_key)
                problem, size, digest = await _check_file(storage, media)
                run.files_checked += 1
                run.bytes_checked += size or 0
                if problem:
                    run.problems += 1
                    session.add(
                        IntegrityIssue(
                            run_id=run.id,
                            media_id=media.id,
                            tree_id=media.tree_id,
                            key=media.original_key,
                            problem=problem,
                            expected_size=media.size,
                            actual_size=size,
                            expected_sha256=media.sha256,
                            actual_sha256=digest,
                        )
                    )
                    logger.warning(
                        "integrity problem",
                        extra={"key": media.original_key, "problem": problem.value},
                    )
            last_id = page[-1].id
            await session.commit()
        run.untracked_files = sum(
            [1 async for key in storage.list_keys(ORIGINALS_PREFIX) if key not in known]
        )
        run.status = IntegrityStatus.done
    except Exception as exc:
        await session.rollback()
        run = await session.get(IntegrityRun, run_id)
        assert run is not None
        run.status = IntegrityStatus.failed
        run.error = str(exc)[:1000]
        logger.exception("integrity check failed")
    run.finished_at = utcnow()
    await session.commit()
    logger.info(
        "integrity check finished",
        extra={
            "status": run.status.value,
            "files": run.files_checked,
            "problems": run.problems,
            "untracked": run.untracked_files,
        },
    )
    return run


async def latest_runs(session: AsyncSession, limit: int = 10) -> list[IntegrityRun]:
    await _close_stale(session)
    return list(
        await session.scalars(
            select(IntegrityRun).order_by(IntegrityRun.started_at.desc()).limit(limit)
        )
    )


async def run_issues(
    session: AsyncSession, run_id: uuid.UUID, limit: int = 500
) -> list[IntegrityIssue]:
    return list(
        await session.scalars(
            select(IntegrityIssue)
            .where(IntegrityIssue.run_id == run_id)
            .order_by(IntegrityIssue.key)
            .limit(limit)
        )
    )


async def originals_total(session: AsyncSession) -> tuple[int, int]:
    """Number and total size of stored originals (for progress)."""
    row = (
        await session.execute(select(func.count(), func.coalesce(func.sum(MediaFile.size), 0)))
    ).one()
    return int(row[0]), int(row[1])


async def user_label(session: AsyncSession, user_id: uuid.UUID | None) -> str | None:
    if user_id is None:
        return None
    user = await session.get(User, user_id)
    return user.display_name if user else None
