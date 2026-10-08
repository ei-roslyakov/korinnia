"""What a GEDCOM file means, in Korinnia's terms: people (names, gender, life events,
notes), families (couples and their children with the kind of link), sources and the
citations attached to facts. Pure data, no database: `services/gedcom_import.py` saves it.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from app.importers.gedcom.dates import parse_date
from app.importers.gedcom.parser import Document, Line

# Individual events and the Korinnia event type they become (None: kept as "custom").
INDIVIDUAL_EVENTS: dict[str, str] = {
    "BIRT": "birth",
    "CHR": "baptism",
    "BAPM": "baptism",
    "DEAT": "death",
    "BURI": "burial",
    "CREM": "burial",
    "EDUC": "education",
    "GRAD": "graduation",
    "OCCU": "occupation",
    "RESI": "residence",
    "EMIG": "emigration",
    "IMMI": "immigration",
    "_MILT": "military_service",
    "_MILI": "military_service",
    "MILI": "military_service",
    "_MILITARY_SERVICE": "military_service",
    "_AWARD": "award",
    "_ILLNESS": "illness",
}
# Custom events: their title (English; editors can rename them).
CUSTOM_EVENTS = {
    "ADOP": "Adoption",
    "BARM": "Bar mitzvah",
    "BASM": "Bat mitzvah",
    "BLES": "Blessing",
    "CHRA": "Adult christening",
    "CONF": "Confirmation",
    "FCOM": "First communion",
    "ORDN": "Ordination",
    "NATU": "Naturalisation",
    "CENS": "Census",
    "PROB": "Probate",
    "WILL": "Will",
    "RETI": "Retirement",
    "PROP": "Property",
    "TITL": "Title",
    "EVEN": "Event",
    "FACT": "Fact",
    "_DEG": "Degree",
    "_ELEC": "Election",
    "_EMPLOY": "Employment",
}
# Attributes stored on the person rather than as events (unless dated or placed).
ATTRIBUTES = {"OCCU": "occupation", "EDUC": "education", "RELI": "religion", "NATI": "nationality"}
# Bookkeeping tags of genealogy programs: never reported as "not imported".
_QUIET = {
    "CHAN", "RIN", "_UID", "UID", "_UPD", "RFN", "AFN", "REFN", "_FSFTID", "_PRIM", "_CUT",
    "_FID", "_WT_USER", "_TID", "_PID", "_APID", "_MTYPE", "_SURN", "_MSTAT", "SUBM", "ANCI",
    "DESI", "_PHOTO", "_PRIMARY", "_PPID", "_PRIM_CUTOUT", "_POSITION", "_PRIV", "RESN",
    "_CREAT", "_EXPORTED_FROM_SITE_ID", "_RTLSAVE", "SEX", "NAME", "FAMC", "FAMS", "NOTE",
    "SOUR", "OBJE", "ASSO", "ALIA", "DSCR", "_MARNM", "HUSB", "WIFE", "CHIL", "NCHI",
    "MARR", "DIV", "ENGA", "MARB", "MARC", "MARL", "MARS", "DIVF", "ANUL", "_SEPR",
}  # fmt: skip

_PATRONYMIC = re.compile(
    r"(ович|евич|йович|ьович|івна|ївна|овна|евна|ична|ічна|"
    r"ovych|ovich|evych|evich|ivna|yivna|ovna|evna|ichna)$",
    re.IGNORECASE,
)


def script_of(text: str) -> str:
    if any("Ѐ" <= c <= "ӿ" for c in text):
        return "cyrillic"
    if any((c.isascii() and c.isalpha()) or "À" <= c <= "ɏ" for c in text):
        return "latin"
    return "other"


@dataclass
class GName:
    type: str = "birth"
    first_name: str | None = None
    middle_name: str | None = None
    patronymic: str | None = None
    last_name: str | None = None
    script: str = "latin"

    def as_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if v is not None}

    @property
    def display(self) -> str:
        return " ".join(p for p in (self.first_name, self.patronymic, self.last_name) if p)


@dataclass
class GCitation:
    source_xref: str | None  # None: an inline source described by `inline_title`
    inline_title: str | None = None
    page: str | None = None
    quality: str | None = None
    notes: str | None = None


@dataclass
class GPlace:
    key: str  # the PLAC text, used to create each place once
    name: str
    region: str | None = None
    country: str | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None


@dataclass
class GEvent:
    type: str
    title: str | None = None
    date: dict[str, Any] | None = None
    place: str | None = None  # GPlace key
    description: str | None = None
    cemetery_name: str | None = None
    citations: list[GCitation] = field(default_factory=list)


@dataclass
class GPerson:
    xref: str
    names: list[GName] = field(default_factory=list)
    gender: str = "unknown"
    events: list[GEvent] = field(default_factory=list)
    attributes: dict[str, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    citations: list[GCitation] = field(default_factory=list)
    # (family xref, kind of link from PEDI) for families this person is a child of.
    child_of: list[tuple[str, str | None]] = field(default_factory=list)
    media_links: int = 0

    @property
    def display(self) -> str:
        return self.names[0].display if self.names else ""

    def vital(self, type_: str) -> GEvent | None:
        return next((e for e in self.events if e.type == type_), None)

    def year(self, type_: str) -> int | None:
        ev = self.vital(type_)
        return ev.date.get("year") if ev and ev.date else None


@dataclass
class GChild:
    xref: str
    # Link kind towards the father and the mother (_FREL / _MREL), if the file says.
    father_type: str | None = None
    mother_type: str | None = None


@dataclass
class GFamily:
    xref: str
    husband: str | None = None
    wife: str | None = None
    children: list[GChild] = field(default_factory=list)
    married: bool = False
    start_date: dict[str, Any] | None = None
    end_date: dict[str, Any] | None = None
    end_reason: str | None = None
    place: str | None = None
    notes: list[str] = field(default_factory=list)
    citations: list[GCitation] = field(default_factory=list)


@dataclass
class GSource:
    xref: str
    title: str
    author: str | None = None
    archive_name: str | None = None
    reference_number: str | None = None
    url: str | None = None
    notes: str | None = None


@dataclass
class GedcomData:
    persons: dict[str, GPerson]
    families: dict[str, GFamily]
    sources: dict[str, GSource]
    places: dict[str, GPlace]
    header: dict[str, str | None]
    encoding: str
    warnings: list[str]
    # Tags that were seen but not imported, with how often (for the preview).
    skipped_tags: Counter[str]
    media_links: int


# --- Helpers ------------------------------------------------------------------------------


# GEDCOM certainty assessment (QUAY 0–3) → citation quality.
_QUALITY = {"3": "primary", "2": "secondary", "1": "unverified", "0": "unverified"}


def _pedi(value: str | None) -> str | None:
    v = (value or "").strip().lower()
    return {
        "birth": "biological",
        "natural": "biological",
        "biological": "biological",
        "adopted": "adoptive",
        "adoptive": "adoptive",
        "foster": "foster",
        "step": "step",
        "stepchild": "step",
        "sealing": None,
        "unknown": "unknown",
    }.get(v)


def _coordinate(value: str | None, positive: str, negative: str) -> Decimal | None:
    if not value:
        return None
    v = value.strip().upper().replace(",", ".")
    sign = 1
    if v[:1] in (positive, negative):
        sign = -1 if v[0] == negative else 1
        v = v[1:]
    try:
        number = Decimal(v) * sign
    except InvalidOperation:
        return None
    return number.quantize(Decimal("0.000001"))


class _Reader:
    def __init__(self, doc: Document) -> None:
        self.doc = doc
        self.warnings: list[str] = []
        self.skipped: Counter[str] = Counter()
        self.places: dict[str, GPlace] = {}
        self.shared_notes = {
            r.xref: r.value.strip() for r in doc.of("NOTE") if r.xref and r.value.strip()
        }
        self.media_links = 0

    def note_text(self, line: Line) -> str | None:
        if line.pointer:
            return self.shared_notes.get(line.pointer)
        return line.value.strip() or None

    def notes(self, line: Line) -> list[str]:
        return [t for n in line.all("NOTE") if (t := self.note_text(n))]

    def citations(self, line: Line) -> list[GCitation]:
        out = []
        for s in line.all("SOUR"):
            quay = s.text("QUAY")
            out.append(
                GCitation(
                    source_xref=s.pointer,
                    inline_title=None if s.pointer else (s.value.strip()[:500] or None),
                    page=(s.text("PAGE") or "")[:300] or None,
                    quality=_QUALITY.get(quay or ""),
                    notes="\n\n".join(
                        self.notes(s) + [t for d in s.all("DATA") if (t := d.text("TEXT"))]
                    )
                    or None,
                )
            )
        return out

    def place(self, line: Line) -> str | None:
        plac = line.first("PLAC")
        if plac is None or not plac.value.strip():
            return None
        key = ", ".join(p.strip() for p in plac.value.split(",") if p.strip())
        if not key:
            return None
        if key not in self.places:
            parts = key.split(", ")
            self.places[key] = GPlace(
                key=key,
                name=parts[0][:300],
                region=", ".join(parts[1:-1])[:200] or None if len(parts) > 2 else None,
                country=parts[-1][:100] if len(parts) > 1 else None,
            )
        place = self.places[key]
        mapl = plac.first("MAP")
        if mapl and place.latitude is None:
            lat = _coordinate(mapl.text("LATI"), "N", "S")
            lon = _coordinate(mapl.text("LONG"), "E", "W")
            if lat is not None and lon is not None and abs(lat) <= 90 and abs(lon) <= 180:
                place.latitude, place.longitude = lat, lon
        return key

    def event(self, line: Line, type_: str, title: str | None = None) -> GEvent:
        description = list(self.notes(line))
        if cause := line.text("CAUS"):
            description.insert(0, f"Cause: {cause}")
        if addr := line.first("ADDR"):
            description.append(addr.value.strip())
        return GEvent(
            type=type_,
            title=title[:300] if title else None,
            date=parse_date(line.text("DATE")),
            place=self.place(line),
            description="\n\n".join(d for d in description if d) or None,
            citations=self.citations(line),
        )

    # --- Records ------------------------------------------------------------------------

    def name(self, line: Line) -> GName:
        raw = line.value.strip()
        m = re.match(r"^(.*?)/(.*?)/(.*)$", raw)
        given, surname = (m.group(1), m.group(2)) if m else (raw, "")
        given = (line.text("GIVN") or given).strip()
        surname = (line.text("SURN") or surname).strip()
        words = given.split()
        patronymic = None
        if len(words) >= 2 and _PATRONYMIC.search(words[-1]):
            patronymic = words.pop()
        name_type = (line.text("TYPE") or "").lower()
        return GName(
            type={"married": "married", "aka": "alias", "nickname": "nickname"}.get(
                name_type, "birth"
            ),
            first_name=words[0][:200] if words else None,
            middle_name=" ".join(words[1:])[:200] or None,
            patronymic=patronymic[:200] if patronymic else None,
            last_name=surname[:200] or None,
            script=script_of(raw),
        )

    def person(self, rec: Line) -> GPerson:
        p = GPerson(xref=rec.xref or "")
        for n in rec.all("NAME"):
            name = self.name(n)
            if name.first_name or name.last_name:
                p.names.append(name)
            for variant in n.all("ROMN", "FONE"):
                v = self.name(variant)
                if (v.first_name or v.last_name) and v.display != name.display:
                    p.names.append(v)
            if marnm := n.text("_MARNM"):
                p.names.append(
                    GName(
                        type="married",
                        first_name=name.first_name,
                        patronymic=name.patronymic,
                        last_name=marnm[:200],
                        script=script_of(marnm),
                    )
                )
            if nick := n.text("NICK"):
                p.names.append(
                    GName(type="nickname", first_name=nick[:200], script=script_of(nick))
                )
        sex = (rec.text("SEX") or "").upper()[:1]
        p.gender = {"M": "male", "F": "female", "X": "other"}.get(sex, "unknown")
        for child in rec.children:
            tag = child.tag
            if tag in ("RELI", "NATI"):
                if child.value.strip():
                    p.attributes.setdefault(ATTRIBUTES[tag], child.value.strip()[:200])
                continue
            if tag in ATTRIBUTES and not child.first("DATE") and not child.first("PLAC"):
                if child.value.strip():
                    key = ATTRIBUTES[tag]
                    existing = p.attributes.get(key)
                    p.attributes[key] = (
                        f"{existing}; {child.value.strip()}" if existing else (child.value.strip())
                    )
                continue
            if tag in INDIVIDUAL_EVENTS:
                title = child.value.strip() if tag in ("OCCU", "EDUC", "GRAD") else None
                if tag == "CREM":
                    title = "Cremation"
                p.events.append(self.event(child, INDIVIDUAL_EVENTS[tag], title))
            elif tag in CUSTOM_EVENTS:
                title = child.text("TYPE") or (child.value.strip() if tag != "EVEN" else None)
                p.events.append(self.event(child, "custom", title or CUSTOM_EVENTS[tag]))
            elif tag == "FAMC" and child.pointer:
                p.child_of.append((child.pointer, _pedi(child.text("PEDI"))))
            elif tag == "OBJE":
                p.media_links += 1
            elif tag not in _QUIET:
                self.skipped[tag] += 1
        p.notes = self.notes(rec)
        if dscr := rec.text("DSCR"):
            p.notes.append(f"Description: {dscr}")
        p.citations = self.citations(rec)
        return p

    def family(self, rec: Line) -> GFamily:
        f = GFamily(xref=rec.xref or "")
        f.husband = (h.pointer if (h := rec.first("HUSB")) else None) or None
        f.wife = (w.pointer if (w := rec.first("WIFE")) else None) or None
        for c in rec.all("CHIL"):
            if c.pointer:
                f.children.append(
                    GChild(
                        xref=c.pointer,
                        father_type=_pedi(c.text("_FREL")),
                        mother_type=_pedi(c.text("_MREL")),
                    )
                )
        marr = rec.first("MARR")
        if marr is not None:
            f.married = True
            f.start_date = parse_date(marr.text("DATE"))
            f.place = self.place(marr)
            f.citations += self.citations(marr)
            f.notes += self.notes(marr)
        for tag, reason in (("DIV", "divorce"), ("ANUL", "other"), ("_SEPR", "separation")):
            if (end := rec.first(tag)) is not None:
                f.end_reason = reason
                f.end_date = parse_date(end.text("DATE"))
                break
        f.notes += self.notes(rec)
        f.citations += self.citations(rec)
        return f

    def source(self, rec: Line) -> GSource:
        repo = rec.first("REPO")
        archive = None
        call_number = None
        if repo is not None:
            call_number = repo.text("CALN")
            target = next((r for r in self.doc.of("REPO") if r.xref == repo.pointer), None)
            archive = (target.text("NAME") if target else None) or (
                repo.value.strip() if not repo.pointer else None
            )
        notes = [t for t in (rec.text("PUBL"), rec.text("TEXT")) if t] + self.notes(rec)
        title = rec.text("TITL") or rec.text("ABBR") or f"Source {rec.xref}"
        return GSource(
            xref=rec.xref or "",
            title=title[:500],
            author=(rec.text("AUTH") or "")[:300] or None,
            archive_name=(archive or "")[:300] or None,
            reference_number=(call_number or "")[:300] or None,
            url=(rec.text("WWW") or rec.text("_URL") or "")[:2000] or None,
            notes="\n\n".join(notes) or None,
        )


def read(doc: Document) -> GedcomData:
    r = _Reader(doc)
    head = doc.header()
    header: dict[str, str | None] = {
        "source": None,
        "version": None,
        "date": None,
    }
    if head is not None:
        src = head.first("SOUR")
        if src is not None:
            program = src.text("NAME") or src.value.strip()
            header["source"] = " ".join(p for p in (program, src.text("VERS")) if p) or None
        gedc = head.first("GEDC")
        header["version"] = gedc.text("VERS") if gedc else None
        header["date"] = head.text("DATE")
    persons = {p.xref: p for rec in doc.of("INDI") if rec.xref and (p := r.person(rec))}
    families = {rec.xref: r.family(rec) for rec in doc.of("FAM") if rec.xref}
    sources = {rec.xref: r.source(rec) for rec in doc.of("SOUR") if rec.xref}
    for p in persons.values():
        if not p.names:
            p.names.append(GName(first_name="?", script="other"))
            r.warnings.append(f"no_name:{p.xref}")
    if doc.bad_lines:
        r.warnings.append(f"bad_lines:{doc.bad_lines}")
    return GedcomData(
        persons=persons,
        families=families,
        sources=sources,
        places=r.places,
        header=header,
        encoding=doc.encoding,
        warnings=r.warnings,
        skipped_tags=r.skipped,
        # Linked from people, or listed as top-level multimedia records.
        media_links=max(
            sum(p.media_links for p in persons.values()), sum(1 for _ in doc.of("OBJE"))
        ),
    )
