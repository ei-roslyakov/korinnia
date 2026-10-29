"""A tree's birthdays, memorial days and wedding anniversaries as an iCalendar feed
(RFC 5545): one yearly, all-day event per exactly dated fact (D115)."""

from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

from app.core.enums import Language

Occasion = Literal["birthday", "memorial", "wedding"]

TEXT: dict[Language, dict[str, str]] = {
    Language.en: {
        "calendar": "{tree}: birthdays and anniversaries",
        "birthday": "Birthday: {names} (b. {year})",
        "memorial": "Memorial day: {names} (d. {year})",
        "wedding": "Wedding anniversary: {names} ({year})",
        "and": " & ",
    },
    Language.uk: {
        "calendar": "{tree}: дні народження й річниці",
        "birthday": "День народження: {names} (нар. {year})",
        "memorial": "День пам’яті: {names} (пом. {year})",
        "wedding": "Річниця весілля: {names} ({year})",
        "and": " і ",
    },
    Language.pl: {
        "calendar": "{tree}: urodziny i rocznice",
        "birthday": "Urodziny: {names} (ur. {year})",
        "memorial": "Dzień pamięci: {names} (zm. {year})",
        "wedding": "Rocznica ślubu: {names} ({year})",
        "and": " i ",
    },
}


@dataclass(frozen=True, slots=True)
class Anniversary:
    occasion: Occasion
    # Stable across fetches, so calendar apps update an event instead of adding a copy.
    uid: str
    date: dt.date
    people: list[tuple[uuid.UUID, str]]  # id, display name


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _ymd(d: dt.date) -> str:
    return f"{d.year:04d}{d.month:02d}{d.day:02d}"  # strftime does not pad years < 1000


def _fold(line: str) -> str:
    """Lines longer than 75 octets continue on the next line after a space (never inside a
    UTF-8 character)."""
    out: list[str] = []
    current, size, limit = "", 0, 75
    for ch in line:
        n = len(ch.encode())
        if size + n > limit:
            out.append(current)
            current, size, limit = " ", 1, 75
        current += ch
        size += n
    out.append(current)
    return "\r\n".join(out)


def render(
    *,
    tree_name: str,
    language: Language,
    items: Iterable[Anniversary],
    person_url: str,
    now: dt.datetime | None = None,
) -> str:
    """`person_url` is a format string with `{id}` for a person's page."""
    text = TEXT[language]
    stamp = (now or dt.datetime.now(dt.UTC)).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Korinnia//Family calendar//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_escape(text['calendar'].format(tree=tree_name))}",
        "REFRESH-INTERVAL;VALUE=DURATION:PT12H",
        "X-PUBLISHED-TTL:PT12H",
    ]
    for a in items:
        names = text["and"].join(name for _, name in a.people)
        if a.date.month == 2 and a.date.day == 29:
            # Remembered on the last day of February in other years.
            rule = "RRULE:FREQ=YEARLY;BYMONTH=2;BYMONTHDAY=-1"
        else:
            rule = "RRULE:FREQ=YEARLY"
        lines += [
            "BEGIN:VEVENT",
            f"UID:{a.uid}",
            f"DTSTAMP:{stamp}",
            f"DTSTART;VALUE=DATE:{_ymd(a.date)}",
            f"DTEND;VALUE=DATE:{_ymd(a.date + dt.timedelta(days=1))}",
            rule,
            f"SUMMARY:{_escape(text[a.occasion].format(names=names, year=a.date.year))}",
            "DESCRIPTION:" + _escape("\n".join(person_url.format(id=pid) for pid, _ in a.people)),
            f"URL:{person_url.format(id=a.people[0][0])}",
            "TRANSP:TRANSPARENT",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return "".join(_fold(line) + "\r\n" for line in lines)
