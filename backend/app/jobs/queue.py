"""Enqueue background work from the API. Failures to enqueue are logged, never raised:
the upload itself succeeded, and a periodic sweep re-queues stuck items."""

from __future__ import annotations

import logging
import uuid

from procrastinate.exceptions import AlreadyEnqueued

from app.jobs.tasks import make_person_avatar, process_media_file

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
