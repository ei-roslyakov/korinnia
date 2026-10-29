"""Calendar feeds (D115): each member may subscribe their calendar app to a tree's
birthdays, memorial days and wedding anniversaries."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Path, Response, status
from pydantic import BaseModel

from app.api.deps import ActorDep, SessionDep, TreeAccess, TreeViewer
from app.core.config import get_settings
from app.core.enums import Language
from app.core.errors import PermissionDeniedError
from app.exporters import ical
from app.models import CalendarFeed
from app.services import calendar_feeds as service
from app.services import visibility

router = APIRouter(tags=["calendar"])


class CalendarFeedOut(BaseModel):
    language: Language
    created_at: datetime
    last_used_at: datetime | None


class CalendarFeedIn(BaseModel):
    language: Language


class CreatedCalendarFeed(BaseModel):
    feed: CalendarFeedOut
    # Shown once: only a hash of the token is stored.
    url: str
    webcal_url: str


def _out(feed: CalendarFeed) -> CalendarFeedOut:
    return CalendarFeedOut(
        language=feed.language, created_at=feed.created_at, last_used_at=feed.last_used_at
    )


def _member(access: TreeAccess) -> None:
    """Feeds belong to members' own accounts: not to share-link visitors or demo accounts."""
    if access.via_share_link:
        raise PermissionDeniedError()
    if access.user.is_sandbox:
        raise PermissionDeniedError("not_in_demo")


@router.get("/trees/{tree_id}/calendar-feed", response_model=CalendarFeedOut)
async def get_feed(access: TreeViewer, session: SessionDep) -> CalendarFeedOut:
    """Your calendar feed of this tree (404 if you have none). The URL itself is not
    stored, so it cannot be shown again."""
    _member(access)
    return _out(await service.get_feed(session, access.tree.id, access.user.id))


@router.post(
    "/trees/{tree_id}/calendar-feed",
    response_model=CreatedCalendarFeed,
    status_code=status.HTTP_201_CREATED,
)
async def create_feed(
    body: CalendarFeedIn, access: TreeViewer, session: SessionDep, actor: ActorDep
) -> CreatedCalendarFeed:
    """A new feed URL for you; a previous one of yours stops working."""
    _member(access)
    feed, token = await service.create_feed(session, access.tree, body.language, actor)
    url = service.feed_url(token)
    return CreatedCalendarFeed(
        feed=_out(feed), url=url, webcal_url=re.sub(r"^https?://", "webcal://", url)
    )


@router.patch("/trees/{tree_id}/calendar-feed", response_model=CalendarFeedOut)
async def update_feed(
    body: CalendarFeedIn, access: TreeViewer, session: SessionDep
) -> CalendarFeedOut:
    """Change the language of the event titles; the URL stays the same."""
    _member(access)
    feed = await service.get_feed(session, access.tree.id, access.user.id)
    return _out(await service.set_language(session, feed, body.language))


@router.delete("/trees/{tree_id}/calendar-feed", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_feed(access: TreeViewer, session: SessionDep, actor: ActorDep) -> None:
    _member(access)
    await service.revoke(
        session, await service.get_feed(session, access.tree.id, access.user.id), actor
    )


@router.get("/calendar/{token}.ics", response_class=Response)
async def calendar(
    token: Annotated[str, Path(min_length=20, max_length=100)], session: SessionDep
) -> Response:
    """The feed itself, for calendar apps (no sign-in: the token is the key). Rendered with
    the owner's current role, so living people's facts follow the tree's privacy setting."""
    feed, tree, role, _ = await service.resolve(session, token)
    seen = await visibility.load(session, tree, role, via_share_link=False)
    items = await service.anniversaries(session, tree.id, seen.protected)
    base = get_settings().public_base_url.rstrip("/")
    text = ical.render(
        tree_name=tree.name,
        language=feed.language,
        items=items,
        person_url=f"{base}/trees/{tree.id}/people/{{id}}",
    )
    return Response(
        content=text.encode(),
        media_type="text/calendar; charset=utf-8",
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{quote(tree.name)}.ics",
            "Cache-Control": "private, max-age=3600",
        },
    )
