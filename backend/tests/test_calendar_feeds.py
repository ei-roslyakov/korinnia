"""Calendar feeds of birthdays, memorial days and wedding anniversaries (D115)."""

from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.enums import Language
from app.exporters.ical import Anniversary, render
from app.models import AuditLog, CalendarFeed, Tree, TreeMembership, TreeRole, User
from tests.conftest import ApiClient
from tests.helpers import Ctx

MakeClient = Callable[[], Awaitable[ApiClient]]


def parse(text: str) -> tuple[dict[str, str], list[dict[str, str]]]:
    """A tiny RFC 5545 reader: unfolds lines, returns calendar and event properties."""
    assert text.endswith("\r\n")
    assert all(len(line.encode()) <= 75 for line in text.split("\r\n"))
    lines = text.replace("\r\n ", "").split("\r\n")
    assert lines[0] == "BEGIN:VCALENDAR"
    assert lines[-2] == "END:VCALENDAR"
    calendar: dict[str, str] = {}
    events: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for line in lines[1:-2]:
        if line == "BEGIN:VEVENT":
            current = {}
        elif line == "END:VEVENT":
            assert current is not None
            events.append(current)
            current = None
        else:
            key, value = line.split(":", 1)
            (current if current is not None else calendar)[key] = value
    return calendar, events


def unescape(value: str) -> str:
    return value.replace("\\n", "\n").replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\")


# --- Rendering ------------------------------------------------------------------------------


def test_render_yearly_all_day_events() -> None:
    a, b = uuid.uuid4(), uuid.uuid4()
    long_name = "Олександра-Вікторія Коваленко-Шевченко-Петренко, у дівоцтві Іваненко"
    items = [
        Anniversary("birthday", "event-1@korinnia", dt.date(1952, 3, 14), [(a, long_name)]),
        Anniversary("memorial", "event-2@korinnia", dt.date(2001, 11, 2), [(b, "Галина")]),
        Anniversary("wedding", "p-3@korinnia", dt.date(1975, 6, 7), [(a, "Іван"), (b, "Галина")]),
        Anniversary("birthday", "event-4@korinnia", dt.date(1952, 2, 29), [(b, "Петро")]),
        Anniversary("birthday", "event-5@korinnia", dt.date(988, 7, 28), [(b, "Володимир")]),
    ]
    text = render(
        tree_name="Родина; Коваленків",
        language=Language.uk,
        items=items,
        person_url="https://k.example/trees/t/people/{id}",
        now=dt.datetime(2026, 10, 29, 12, tzinfo=dt.UTC),
    )
    calendar, events = parse(text)
    assert calendar["VERSION"] == "2.0"
    assert unescape(calendar["X-WR-CALNAME"]) == "Родина; Коваленків: дні народження й річниці"
    assert [e["UID"] for e in events] == [i.uid for i in items]
    birthday, memorial, wedding, leap, old = events
    assert birthday["DTSTART;VALUE=DATE"] == "19520314"
    assert birthday["DTEND;VALUE=DATE"] == "19520315"
    assert birthday["RRULE"] == "FREQ=YEARLY"
    assert unescape(birthday["SUMMARY"]) == f"День народження: {long_name} (нар. 1952)"
    assert birthday["DTSTAMP"] == "20261029T120000Z"
    assert unescape(memorial["SUMMARY"]) == "День пам’яті: Галина (пом. 2001)"
    assert unescape(wedding["SUMMARY"]) == "Річниця весілля: Іван і Галина (1975)"
    assert unescape(wedding["DESCRIPTION"]).split("\n") == [
        f"https://k.example/trees/t/people/{a}",
        f"https://k.example/trees/t/people/{b}",
    ]
    assert leap["RRULE"] == "FREQ=YEARLY;BYMONTH=2;BYMONTHDAY=-1"
    assert old["DTSTART;VALUE=DATE"] == "09880728"


@pytest.mark.parametrize(
    ("language", "summary"),
    [
        (Language.en, "Wedding anniversary: Ivan & Halyna (1975)"),
        (Language.pl, "Rocznica ślubu: Ivan i Halyna (1975)"),
    ],
)
def test_render_in_other_languages(language: Language, summary: str) -> None:
    item = Anniversary(
        "wedding",
        "x@korinnia",
        dt.date(1975, 6, 7),
        [(uuid.uuid4(), "Ivan"), (uuid.uuid4(), "Halyna")],
    )
    _, events = parse(render(tree_name="T", language=language, items=[item], person_url="{id}"))
    assert unescape(events[0]["SUMMARY"]) == summary


# --- API ------------------------------------------------------------------------------------


async def _family(ctx: Ctx) -> dict[str, Any]:
    halyna = await ctx.person(
        "Галина",
        birth={"date": {"year": 1923, "month": 5, "day": 2}},
        death={"date": {"year": 2001, "month": 11, "day": 2}},
    )
    ivan = await ctx.person("Іван", birth={"date": {"year": 1920}}, death={"date": {"year": 1990}})
    olena = await ctx.person("Олена", birth={"date": {"year": 1985, "month": 3, "day": 14}})
    unknown_day = await ctx.person("Петро", birth={"date": {"year": 1950, "month": 4}})
    resp = await ctx.editor.post(
        f"{ctx.base}/partnerships",
        json={
            "person_a_id": ivan["id"],
            "person_b_id": halyna["id"],
            "type": "marriage",
            "start_date": {"year": 1946, "month": 6, "day": 7},
        },
    )
    assert resp.status_code == 201, resp.text
    return {"halyna": halyna, "ivan": ivan, "olena": olena, "petro": unknown_day}


def _path(url: str) -> str:
    return "/" + url.split("://", 1)[1].split("/", 1)[1]


async def test_feed_lifecycle(ctx: Ctx, make_client: MakeClient, session: AsyncSession) -> None:
    people = await _family(ctx)
    assert (await ctx.editor.get(f"{ctx.base}/calendar-feed")).status_code == 404
    created = await ctx.editor.post(f"{ctx.base}/calendar-feed", json={"language": "en"})
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["url"].startswith(get_settings().public_base_url.rstrip("/") + "/api/v1/calendar/")
    assert body["url"].endswith(".ics")
    assert body["webcal_url"].startswith("webcal://")
    token = body["url"].rsplit("/", 1)[1].removesuffix(".ics")
    row = await session.scalar(select(CalendarFeed))
    assert row is not None
    assert token not in row.token_hash

    # Calendar apps send no cookies.
    app_client = await make_client()
    resp = await app_client.get(_path(body["url"]))
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("text/calendar")
    calendar, events = parse(resp.text)
    assert calendar["X-WR-CALNAME"] == "Rosliakov family: birthdays and anniversaries"
    summaries = sorted(e["SUMMARY"] for e in events)
    assert summaries == sorted(
        [
            "Birthday: Галина Коваленко (b. 1923)",
            "Memorial day: Галина Коваленко (d. 2001)",
            "Birthday: Олена Коваленко (b. 1985)",
            "Wedding anniversary: Іван Коваленко & Галина Коваленко (1946)",
        ]
    )  # Ivan's and Petro's dates are not exact: skipped.
    uids = {e["UID"] for e in events}
    again = parse((await app_client.get(_path(body["url"]))).text)[1]
    assert {e["UID"] for e in again} == uids  # stable: apps update instead of duplicating
    olena = next(e for e in events if "Олена" in e["SUMMARY"])
    assert people["olena"]["id"] in unescape(olena["DESCRIPTION"])

    status = (await ctx.editor.get(f"{ctx.base}/calendar-feed")).json()
    assert status["language"] == "en"
    assert status["last_used_at"] is not None

    # The language changes without a new URL.
    resp = await ctx.editor.patch(f"{ctx.base}/calendar-feed", json={"language": "uk"})
    assert resp.json()["language"] == "uk"
    text = (await app_client.get(_path(body["url"]))).text
    assert "День народження: Олена Коваленко (нар. 1985)" in unescape(text.replace("\r\n ", ""))

    # A new link replaces the old one.
    renewed = (await ctx.editor.post(f"{ctx.base}/calendar-feed", json={"language": "pl"})).json()
    assert (await app_client.get(_path(body["url"]))).status_code == 404
    assert (await app_client.get(_path(renewed["url"]))).status_code == 200

    # Revoking deletes it.
    assert (await ctx.editor.delete(f"{ctx.base}/calendar-feed")).status_code == 204
    assert (await app_client.get(_path(renewed["url"]))).status_code == 404
    assert (await session.scalar(select(CalendarFeed))) is None
    actions = set((await session.scalars(select(AuditLog.action))).all())
    assert {"calendar_feed.create", "calendar_feed.revoke"} <= actions
    assert (await app_client.get("/api/v1/calendar/" + "x" * 43 + ".ics")).status_code == 404


async def test_feed_follows_membership_and_privacy(
    ctx: Ctx,
    make_client: MakeClient,
    make_user: Callable[..., Awaitable[User]],
    add_member: Callable[..., Awaitable[TreeMembership]],
    session: AsyncSession,
) -> None:
    await _family(ctx)
    viewer_user = await make_user("viewer@example.com")
    tree = await session.get(Tree, ctx.tree.id)
    membership = await add_member(tree, viewer_user, TreeRole.viewer)
    viewer = await make_client()
    await viewer.login("viewer@example.com")
    url = (await viewer.post(f"{ctx.base}/calendar-feed", json={"language": "uk"})).json()["url"]
    app_client = await make_client()

    def names(text: str) -> str:
        return unescape(text.replace("\r\n ", ""))

    assert "Олена" in names((await app_client.get(_path(url))).text)
    # Viewers who see only the basics of living people get no living birthdays.
    await ctx.editor.patch(ctx.base, json={"living_privacy": "viewers_and_share_links"})
    text = names((await app_client.get(_path(url))).text)
    assert "Олена" not in text
    assert "Галина" in text

    # Removed from the tree: the feed stops working.
    await session.delete(membership)
    await session.commit()
    assert (await app_client.get(_path(url))).status_code == 404


async def test_share_link_visitors_cannot_create_feeds(ctx: Ctx, make_client: MakeClient) -> None:
    link = (await ctx.editor.post(f"{ctx.base}/share-links", json={})).json()
    guest = await make_client()
    await guest.post(f"/api/v1/share/{link['url'].rsplit('/s/', 1)[1]}/open")
    assert (await guest.get(f"{ctx.base}/calendar-feed")).status_code == 403
    resp = await guest.post(f"{ctx.base}/calendar-feed", json={"language": "uk"})
    assert resp.status_code == 403  # writes are refused for link visitors anyway


async def test_feed_is_rate_limited(
    ctx: Ctx, make_client: MakeClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "calendar_feed_requests_per_hour", 2)
    url = (await ctx.editor.post(f"{ctx.base}/calendar-feed", json={"language": "en"})).json()[
        "url"
    ]
    app_client = await make_client()
    assert (await app_client.get(_path(url))).status_code == 200
    assert (await app_client.get(_path(url))).status_code == 200
    resp = await app_client.get(_path(url))
    assert (resp.status_code, resp.json()["code"]) == (429, "too_many_attempts")
