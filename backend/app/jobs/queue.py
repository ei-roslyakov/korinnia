"""Enqueue background work from the API. Failures to enqueue are logged, never raised:
the upload itself succeeded, and a periodic sweep re-queues stuck items."""

from __future__ import annotations

import logging
import uuid

from procrastinate.exceptions import AlreadyEnqueued

from app.jobs.tasks import (
    analyze_gedcom,
    apply_gedcom,
    check_integrity,
    create_demo_tree,
    make_person_avatar,
    process_demo_portraits,
    process_media_file,
    undo_gedcom,
)

logger = logging.getLogger(__name__)


async def enqueue_media_processing(media_id: uuid.UUID) -> None:
    try:
        await process_media_file.configure(queueing_lock=f"media:{media_id}").defer_async(
            media_id=str(media_id)
        )
    except AlreadyEnqueued:
        pass
    except Exception:
        logger.exception("could not enqueue media processing", extra={"media_id": str(media_id)})


async def enqueue_avatar(person_id: uuid.UUID) -> None:
    try:
        await make_person_avatar.configure(queueing_lock=f"avatar:{person_id}").defer_async(
            person_id=str(person_id)
        )
    except AlreadyEnqueued:
        pass
    except Exception:
        logger.exception("could not enqueue portrait", extra={"person_id": str(person_id)})


async def enqueue_demo_tree(user_id: uuid.UUID) -> None:
    """Build the user's own copy of the demo family in the background."""
    try:
        await create_demo_tree.configure(queueing_lock=f"demo:{user_id}").defer_async(
            user_id=str(user_id)
        )
    except AlreadyEnqueued:
        pass
    except Exception:
        logger.exception("could not enqueue demo tree", extra={"user_id": str(user_id)})


async def enqueue_demo_portraits(tree_id: uuid.UUID) -> None:
    try:
        await process_demo_portraits.configure(
            queueing_lock=f"demo-portraits:{tree_id}"
        ).defer_async(tree_id=str(tree_id))
    except AlreadyEnqueued:
        pass
    except Exception:
        logger.exception("could not enqueue demo portraits", extra={"tree_id": str(tree_id)})


async def enqueue_integrity_check(run_id: uuid.UUID) -> None:
    """Raises if the job cannot be queued: the caller marks the run as failed."""
    await check_integrity.configure(queueing_lock="integrity").defer_async(run_id=str(run_id))


async def enqueue_gedcom(step: str, import_id: uuid.UUID) -> None:
    """step: analyze | apply | undo. Raises if the job cannot be queued."""
    task = {"analyze": analyze_gedcom, "apply": apply_gedcom, "undo": undo_gedcom}[step]
    await task.configure(queueing_lock=f"gedcom:{step}:{import_id}").defer_async(
        import_id=str(import_id)
    )
