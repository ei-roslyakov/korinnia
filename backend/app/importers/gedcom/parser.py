"""GEDCOM 5.5 / 5.5.1 reader: bytes → decoded text → a tree of lines.

Only the file structure is handled here (encoding, levels, cross-references, CONT/CONC
continuation lines). What the records mean is in `records.py`.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterator
from dataclasses import dataclass, field

from app.importers.gedcom.ansel import decode_ansel

_LINE_RE = re.compile(r"^\s*(\d{1,2})\s+(?:(@[^@\s][^@]*@)\s+)?([A-Za-z0-9_]+)(?: (.*))?$")


class GedcomError(ValueError):
    """The file is not a GEDCOM file (or cannot be read at all)."""


@dataclass
class Line:
    level: int
    tag: str
    value: str = ""
    xref: str | None = None
    children: list[Line] = field(default_factory=list)

    def first(self, tag: str) -> Line | None:
        return next((c for c in self.children if c.tag == tag), None)

    def all(self, *tags: str) -> list[Line]:
        return [c for c in self.children if c.tag in tags]

    def text(self, tag: str) -> str | None:
        child = self.first(tag)
        return child.value.strip() or None if child else None

    @property
    def pointer(self) -> str | None:
        """The value as a cross-reference ("@I1@"), if it is one."""
        v = self.value.strip()
        return v if len(v) > 2 and v.startswith("@") and v.endswith("@") else None


@dataclass
class Document:
    records: list[Line]
    encoding: str
    # Lines that could not be read (kept for the preview's warnings).
    bad_lines: int = 0

    def header(self) -> Line | None:
        return next((r for r in self.records if r.tag == "HEAD"), None)

    def of(self, tag: str) -> Iterator[Line]:
        return (r for r in self.records if r.tag == tag)


def _declared_charset(raw: bytes) -> str | None:
    """The `1 CHAR …` value from the header (read as ASCII)."""
    head = raw[:4000].decode("ascii", errors="ignore")
    m = re.search(r"^\s*1\s+CHAR\s+(\S+)", head, re.MULTILINE)
    return m.group(1).upper() if m else None


def _cyrillic_share(text: str) -> float:
    """Share of words with non-ASCII letters that are entirely Cyrillic. Western text read
    with the Cyrillic code page gives mixed words ("Mьller"); real Cyrillic text does not."""
    words = [w for w in re.findall(r"[^\W\d_]+", text) if not w.isascii()]
    if not words:
        return 0.0
    return sum(all("\u0400" <= c <= "\u04ff" for c in w) for w in words) / len(words)


def decode(raw: bytes) -> tuple[str, str]:
    """(text, encoding name). Byte-order marks win over the header's CHAR, and a file that
    is valid UTF-8 is read as UTF-8 whatever it claims (many programs mislabel it)."""
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw[3:].decode("utf-8", errors="replace"), "UTF-8"
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16", errors="replace").lstrip("﻿"), "UTF-16"
    if raw[:2] == b"0\x00":
        return raw.decode("utf-16-le", errors="replace"), "UTF-16"
    if raw[:2] == b"\x000":
        return raw.decode("utf-16-be", errors="replace"), "UTF-16"
    charset = _declared_charset(raw)
    try:
        return raw.decode("utf-8"), "UTF-8"
    except UnicodeDecodeError:
        pass
    if charset == "ANSEL":
        return decode_ansel(raw), "ANSEL"
    # "ANSI" means the Windows code page of whoever exported it: Cyrillic (1251) for most
    # Ukrainian files, Western European (1252) otherwise.
    cp1251 = raw.decode("cp1251", errors="replace")
    if (charset and "1251" in charset) or _cyrillic_share(cp1251) > 0.5:
        return cp1251, "Windows-1251"
    return raw.decode("cp1252", errors="replace"), "Windows-1252"


def parse(raw: bytes) -> Document:
    text, encoding = decode(raw)
    text = unicodedata.normalize("NFC", text)
    roots: list[Line] = []
    stack: list[Line] = []
    bad = 0
    for raw_line in text.splitlines():
        if not raw_line.strip():
            continue
        m = _LINE_RE.match(raw_line)
        if not m:
            bad += 1
            continue
        level = int(m.group(1))
        tag = m.group(3).upper()
        value = m.group(4) or ""
        if level == 0:
            line = Line(level=0, tag=tag, value=value, xref=m.group(2))
            roots.append(line)
            stack = [line]
            continue
        # A line belongs to the nearest previous line one level up.
        while stack and stack[-1].level >= level:
            stack.pop()
        if not stack or stack[-1].level != level - 1:
            bad += 1
            continue
        parent = stack[-1]
        if tag == "CONT":
            parent.value += "\n" + value
            continue
        if tag == "CONC":
            parent.value += value
            continue
        line = Line(level=level, tag=tag, value=value, xref=m.group(2))
        parent.children.append(line)
        stack.append(line)
    if not roots or roots[0].tag != "HEAD":
        raise GedcomError("not_gedcom")
    return Document(records=roots, encoding=encoding, bad_lines=bad)


def looks_like_gedcom(raw: bytes) -> bool:
    """Cheap check before storing an upload: the file starts with a `0 HEAD` line."""
    head = raw[:200]
    for bom in (b"\xef\xbb\xbf",):
        head = head.removeprefix(bom)
    if head.startswith((b"\xff\xfe", b"\xfe\xff")) or head[:2] in (b"0\x00", b"\x000"):
        head = head.decode("utf-16", errors="ignore").encode("ascii", errors="ignore")
    return re.match(rb"^\s*0\s+HEAD\b", head) is not None
