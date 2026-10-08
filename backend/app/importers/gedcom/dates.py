"""GEDCOM dates → partial dates (the `PartialDateIn` fields).

Handles exact / month / year dates, ABT / CAL / EST (about), BEF, AFT, BET … AND …,
FROM … TO …, dual years ("1750/51"), calendar escapes (@#DJULIAN@ …) and phrases
("(at Easter)", INT … (phrase)). What cannot be read keeps its original wording as
`phrase`, so nothing is lost.
"""

from __future__ import annotations

import calendar
import re
from typing import Any

_MONTHS = {
    m: i
    for i, m in enumerate(
        ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"],
        start=1,
    )
}
# French republican / Hebrew months are not converted; such dates keep their wording.
_CALENDAR_RE = re.compile(r"@#D([A-Z ]+)@\s*")
_YEAR_RE = re.compile(r"^(\d{1,4})(?:/\d{1,2})?(?:\s*(B\.?C\.?))?$")


def _simple(text: str) -> tuple[int, int | None, int | None] | None:
    """Read "12 MAR 1890", "MAR 1890" or "1890" (also "1750/51") as (year, month, day)."""
    parts = text.upper().split()
    if not parts or len(parts) > 3:
        return None
    m = _YEAR_RE.match(parts[-1])
    if not m or m.group(2):  # B.C. dates are not supported
        return None
    year = int(m.group(1))
    if not 1 <= year <= 9999:
        return None
    month = day = None
    if len(parts) >= 2:
        month = _MONTHS.get(parts[-2][:3])
        if month is None:
            return None
    if len(parts) == 3:
        if not parts[0].isdigit():
            return None
        day = int(parts[0])
        assert month is not None
        if not 1 <= day <= calendar.monthrange(year, month)[1]:
            return None
    return year, month, day


def _ymd(prefix: str, ymd: tuple[int, int | None, int | None]) -> dict[str, Any]:
    y, m, d = ymd
    return {f"{prefix}year": y, f"{prefix}month": m, f"{prefix}day": d}


def parse_date(value: str | None) -> dict[str, Any] | None:
    """A `PartialDateIn`-shaped dict, or None for an empty value."""
    if not value or not value.strip():
        return None
    original = " ".join(value.split())
    text = _CALENDAR_RE.sub("", original).strip()
    upper = text.upper()
    phrase = None
    m = re.match(r"^INT\s+(.*?)\s*\((.*)\)\s*$", text, re.IGNORECASE)
    if m:  # interpreted date with its original wording
        text, upper, phrase = m.group(1), m.group(1).upper(), m.group(2).strip() or None
    elif upper.startswith("(") and upper.endswith(")"):
        return {"precision": "unknown", "phrase": text[1:-1].strip()[:200] or original[:200]}

    def with_phrase(d: dict[str, Any]) -> dict[str, Any]:
        if phrase:
            d["phrase"] = phrase[:200]
        return d

    for keyword in ("ABT", "CAL", "EST", "ABOUT", "CIRCA", "C."):
        if upper.startswith(keyword + " "):
            ymd = _simple(text[len(keyword) + 1 :])
            if ymd:
                return with_phrase({**_ymd("", ymd), "precision": "approx"})
    for keyword, precision in (("BEF", "before"), ("AFT", "after"), ("TO", "before")):
        if upper.startswith(keyword + " "):
            ymd = _simple(text[len(keyword) + 1 :])
            if ymd:
                return with_phrase({**_ymd("", ymd), "precision": precision})
    m = re.match(r"^(?:BET|FROM)\s+(.+?)\s+(?:AND|TO)\s+(.+)$", text, re.IGNORECASE)
    if m:
        a, b = _simple(m.group(1)), _simple(m.group(2))
        if a and b and (b[0], b[1] or 12, b[2] or 31) >= (a[0], a[1] or 1, a[2] or 1):
            return with_phrase({**_ymd("", a), **_ymd("end_", b), "precision": "between"})
    m = re.match(r"^FROM\s+(.+)$", text, re.IGNORECASE)
    if m and (ymd := _simple(m.group(1))):
        return with_phrase({**_ymd("", ymd), "precision": "after"})
    ymd = _simple(text)
    if ymd:
        _, mo, d = ymd
        precision = "exact" if d else "month" if mo else "year"
        return with_phrase({**_ymd("", ymd), "precision": precision})
    return {"precision": "unknown", "phrase": original[:200]}
