"""Calendar feeds (D115): a member subscribes their calendar app to a tree's birthdays,
memorial days and wedding anniversaries. Calendar apps cannot sign in, so the feed URL
carries a secret token; only its SHA-256 is stored and the URL is shown once."""

from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import Collection
from datetime import timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.enums import EventType, Language, ParticipantRole, PartnershipType, TreeRole
from app.core.errors import NotFoundError, TooManyRequestsError
from app.core.security import generate_url_token, hash_token, utcnow
from app.exporters.ical import Anniversary, Occasion
from app.models import CalendarFeed, Tree, User
from app.services import audit
from app.services.context import Actor
from app.services.genealogy.facts import FactRow, exactly_dated, load_facts
from app.services.trees import get_tree_role

WINDOW = timedelta(hours=1)


def feed_url(token: str) -> str:
    return f"{get_settings().public_base_url.rstrip('/')}/api/v1/calendar/{token}.ics"


async def get_feed(session: AsyncSession, tree_id: uuid.UUID, user_id: uuid.UUID) -> CalendarFeed:
    feed = await session.scalar(
        select(CalendarFeed).where(CalendarFeed.tree_id == tree_id, CalendarFeed.user_id == user_id)
    )
    if feed is None:
        raise NotFoundError("calendar_feed_not_found")
    return feed


async def create_feed(
    session: AsyncSession, tree: Tree, language: Language, actor: Actor
) -> tuple[CalendarFeed, str]:
    """A new feed for the acting member; an earlier one of theirs stops working."""
    assert actor.user is not None
    await session.execute(
        delete(CalendarFeed).where(
            CalendarFeed.tree_id == tree.id, CalendarFeed.user_id == actor.user.id
        )
    )
    token = generate_url_token()
    feed = CalendarFeed(
        id=uuid.uuid4(),
        tree_id=tree.id,
        user_id=actor.user.id,
        token_hash=hash_token(token),
        language=language,
        window_count=0,
    )
    session.add(feed)
    audit.record(
        session, actor, "calendar_feed.create", "calendar_feed", feed.id, tree_id=tree.id,
        after={"language": language.value},
    )  # fmt: skip
    await session.commit()
    await session.refresh(feed)
    return feed, token


async def set_language(
    session: AsyncSession, feed: CalendarFeed, language: Language
) -> CalendarFeed:
    feed.language = language
    await session.commit()
    await session.refresh(feed)
    return feed


async def revoke(session: AsyncSession, feed: CalendarFeed, actor: Actor) -> None:
    await session.delete(feed)
    audit.record(
        session, actor, "calendar_feed.revoke", "calendar_feed", feed.id, tree_id=feed.tree_id
    )
    await session.commit()


async def resolve(session: AsyncSession, token: str) -> tuple[CalendarFeed, Tree, TreeRole, User]:
    """The feed, its tree and its owner's current role. 404 for an unknown token or when the
    owner is no longer a member (or no longer active); 429 above the hourly limit."""
    feed = await session.scalar(
        select(CalendarFeed).where(CalendarFeed.token_hash == hash_token(token))
    )
    user = await session.get(User, feed.user_id) if feed else None
    found = await get_tree_role(session, feed.tree_id, user) if feed and user else None
    if feed is None or user is None or not user.is_active or found is None:
        raise NotFoundError("calendar_feed_not_found")
    now = utcnow()
    started = feed.window_started_at
    if started is None or now - started >= WINDOW:
        started = feed.window_started_at = now
        feed.window_count = 0
    feed.window_count += 1
    feed.last_used_at = now
    await session.commit()
    if feed.window_count > get_settings().calendar_feed_requests_per_hour:
        retry = WINDOW - (now - started)
        raise TooManyRequestsError(max(int(retry.total_seconds()), 1))
    tree, role = found
    return feed, tree, role, user


def _occasion(r: FactRow) -> Occasion | None:
    if r.kind == "event":
        return {
            EventType.birth.value: "birthday",
            EventType.death.value: "memorial",
            EventType.marriage.value: "wedding",
        }.get(r.type)  # type: ignore[return-value]
    if r.kind == "partnership_start" and r.type == PartnershipType.marriage.value:
        return "wedding"
    return None


async def anniversaries(
    session: AsyncSession, tree_id: uuid.UUID, hidden: Collection[uuid.UUID] = ()
) -> list[Anniversary]:
    """Birthdays, memorial days and weddings with a known day, month and year; facts of
    `hidden` people (living, for readers who see only their basics) are left out."""
    facts = await load_facts(session, tree_id, hidden)
    out: list[Anniversary] = []
    for r in facts.rows:
        occasion = _occasion(r)
        if occasion is None or not exactly_dated(r):
            continue
        roles = (
            (ParticipantRole.principal, ParticipantRole.spouse)
            if occasion == "wedding"
            else (ParticipantRole.principal,)
        )
        people = [(pid, facts.names[pid]) for pid, role in r.persons if role in roles]
        if not people:
            continue
        assert r.date.year
        assert r.date.month
        assert r.date.day
        out.append(
            Anniversary(
                occasion=occasion,
                uid=f"{r.kind}-{r.id}@korinnia",
                date=dt.date(r.date.year, r.date.month, r.date.day),
                people=people,
            )
        )
    out.sort(key=lambda a: (a.date.month, a.date.day, a.uid))
    return out
