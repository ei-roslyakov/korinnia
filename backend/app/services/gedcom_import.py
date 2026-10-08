"""GEDCOM import (phase 9): upload → analysis with a preview → the user's choices → import
in one transaction → (optionally) undo.

Everything is created through the normal services, so imported people get revisions, audit
entries, validation and warnings like anything entered by hand. One bad record (say, a
third biological parent) is skipped with a warning instead of failing the whole import:
each item is written inside its own savepoint.
"""

from __future__ import annotations

import io
import logging
import uuid
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import DatePrecision, ImportStatus
from app.core.errors import AppError, ConflictError, NotFoundError
from app.core.security import utcnow
from app.importers.gedcom.parser import GedcomError, parse
from app.importers.gedcom.records import GCitation, GedcomData, GEvent, GPerson, read
from app.models import (
    Event,
    EventParticipant,
    GedcomImport,
    Partnership,
    Person,
    PersonName,
    Place,
    Source,
    Tree,
    User,
)
from app.schemas.dates import PartialDateIn
from app.schemas.events import EventCreate
from app.schemas.persons import PersonCreate
from app.schemas.places import PlaceCreate
from app.schemas.relationships import ParentChildCreate, PartnershipCreate
from app.schemas.sources import CitationCreate, SourceCreate
from app.services import audit
from app.services.context import Actor
from app.services.genealogy import events as event_service
from app.services.genealogy import persons as person_service
from app.services.genealogy import places as place_service
from app.services.genealogy import relationships as rel_service
from app.services.genealogy import sources as source_service
from app.services.genealogy import trash
from app.services.genealogy.vitals import load_vitals
from app.services.search_text import normalize, transliterate_uk
from app.storage import Storage

logger = logging.getLogger(__name__)

MAX_FILE_BYTES = 50 * 1024 * 1024
PREVIEW_PEOPLE = 1000
MAX_WARNINGS = 300


# --- Upload --------------------------------------------------------------------------------


async def create_import(
    session: AsyncSession,
    storage: Storage,
    tree: Tree,
    *,
    filename: str,
    raw: bytes,
    actor: Actor,
) -> GedcomImport:
    imp = GedcomImport(
        id=uuid.uuid4(),
        tree_id=tree.id,
        created_by_id=actor.user.id if actor.user else None,
        status=ImportStatus.analyzing,
        filename=filename[:500] or "family.ged",
        size=len(raw),
        file_key="",
        sha256="",
    )
    stored = await storage.put(f"imports/{tree.id}/{imp.id}.ged", io.BytesIO(raw))
    imp.file_key, imp.sha256 = stored.key, stored.sha256
    session.add(imp)
    audit.record(
        session,
        actor,
        "import.upload",
        "gedcom_import",
        imp.id,
        tree_id=tree.id,
        after={"filename": imp.filename, "size": imp.size},
    )
    await session.commit()
    return imp


async def get_import(
    session: AsyncSession, tree_id: uuid.UUID, import_id: uuid.UUID
) -> GedcomImport:
    imp = await session.get(GedcomImport, import_id)
    if imp is None or imp.tree_id != tree_id:
        raise NotFoundError("import_not_found")
    return imp


async def list_imports(session: AsyncSession, tree_id: uuid.UUID) -> list[GedcomImport]:
    return list(
        await session.scalars(
            select(GedcomImport)
            .where(GedcomImport.tree_id == tree_id)
            .order_by(GedcomImport.created_at.desc())
            .limit(20)
        )
    )


async def _load(storage: Storage, imp: GedcomImport) -> GedcomData:
    return read(parse(await storage.read_bytes(imp.file_key)))


# --- Analysis -------------------------------------------------------------------------------


def _name_keys(first: str | None, last: str | None) -> set[tuple[str, str]]:
    """Spelling-insensitive (first name, surname) keys: Cyrillic and Latin spellings of the
    same name meet in their transliteration."""
    given, surname = normalize(first or "").split(), normalize(last or "").split()
    if not given or not surname:
        return set()
    return {
        (given[0], surname[-1]),
        (transliterate_uk(given[0]), transliterate_uk(surname[-1])),
    }


def _year(d: dict[str, Any] | None) -> int | None:
    return d.get("year") if d else None


def _years(birth: int | None, death: int | None) -> str:
    if birth is None and death is None:
        return ""
    return f"{birth or '?'} – {death or ''}".strip(" –") if death else f"{birth}"


@dataclass
class _Existing:
    id: uuid.UUID
    name: str
    gender: str
    birth: int | None
    death: int | None
    keys: set[tuple[str, str]] = field(default_factory=set)


async def _existing_people(session: AsyncSession, tree_id: uuid.UUID) -> list[_Existing]:
    persons = {
        p.id: p
        for p in await session.scalars(
            select(Person).where(Person.tree_id == tree_id, Person.deleted_at.is_(None))
        )
    }
    if not persons:
        return []
    names: dict[uuid.UUID, list[PersonName]] = {}
    for n in await session.scalars(
        select(PersonName).where(PersonName.person_id.in_(persons.keys()))
    ):
        names.setdefault(n.person_id, []).append(n)
    vitals = await load_vitals(session, tree_id, persons.keys())
    out = []
    for pid, person in persons.items():
        own = sorted(names.get(pid, []), key=lambda n: (not n.is_primary, n.sort_order))
        v = vitals.get(pid)
        e = _Existing(
            id=pid,
            name=" ".join(x for x in (own[0].first_name, own[0].patronymic, own[0].last_name) if x)
            if own
            else "",
            gender=person.gender.value,
            birth=v.birth_date.year if v and v.birth_date else None,
            death=v.death_date.year if v and v.death_date else None,
        )
        for n in own:
            for last in (n.last_name, n.maiden_name):
                e.keys |= _name_keys(n.first_name, last)
        out.append(e)
    return out


def find_duplicates(data: GedcomData, existing: list[_Existing]) -> list[dict[str, Any]]:
    """People in the file who look like someone already in the tree: same first name and
    surname (in any spelling), compatible gender, birth years at most 2 apart. "strong"
    when both birth years are known and agree."""
    by_key: dict[tuple[str, str], list[_Existing]] = {}
    for e in existing:
        for k in e.keys:
            by_key.setdefault(k, []).append(e)
    out = []
    for p in data.persons.values():
        keys = set().union(*(_name_keys(n.first_name, n.last_name) for n in p.names))
        candidates = {e.id: e for k in keys for e in by_key.get(k, [])}
        birth = p.year("birth")
        best: tuple[int, _Existing] | None = None
        for e in candidates.values():
            if "unknown" not in (p.gender, e.gender) and p.gender != e.gender:
                continue
            if birth is not None and e.birth is not None:
                if abs(birth - e.birth) > 2:
                    continue
                score = 2
            else:
                score = 1
            if best is None or score > best[0]:
                best = (score, e)
        if best:
            score, e = best
            out.append(
                {
                    "xref": p.xref,
                    "name": p.display,
                    "years": _years(birth, p.year("death")),
                    "strong": score == 2,
                    "existing": {
                        "id": str(e.id),
                        "name": e.name,
                        "years": _years(e.birth, e.death),
                    },
                }
            )
    return out


def _counts(data: GedcomData) -> dict[str, int]:
    parent_links = sum(
        len(f.children) * sum(1 for x in (f.husband, f.wife) if x in data.persons)
        for f in data.families.values()
    )
    citations = sum(
        len(p.citations) + sum(len(e.citations) for e in p.events) for p in data.persons.values()
    ) + sum(len(f.citations) for f in data.families.values())
    return {
        "persons": len(data.persons),
        "families": len(data.families),
        "partnerships": sum(
            1
            for f in data.families.values()
            if f.husband in data.persons and f.wife in data.persons
        ),
        "parent_links": parent_links,
        "events": sum(len(p.events) for p in data.persons.values()),
        "places": len(data.places),
        "sources": len(data.sources),
        "citations": citations,
        "notes": sum(len(p.notes) for p in data.persons.values()),
        "media_links": data.media_links,
    }


def _warnings(data: GedcomData) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    codes = Counter(w.split(":", 1)[0] for w in data.warnings)
    for code, n in codes.items():
        if code == "bad_lines":
            n = sum(int(w.split(":", 1)[1]) for w in data.warnings if w.startswith("bad_lines:"))
        out.append({"code": code, "count": n})
    missing = sum(
        1
        for f in data.families.values()
        for x in (f.husband, f.wife, *(c.xref for c in f.children))
        if x and x not in data.persons
    )
    if missing:
        out.append({"code": "missing_people", "count": missing})
    if data.media_links:
        out.append({"code": "media_not_imported", "count": data.media_links})
    return out


async def analyze(session: AsyncSession, storage: Storage, import_id: uuid.UUID) -> None:
    imp = await session.get(GedcomImport, import_id)
    if imp is None or imp.status != ImportStatus.analyzing:
        return
    try:
        data = await _load(storage, imp)
    except GedcomError as exc:
        imp.status, imp.error = ImportStatus.failed, str(exc)
        await session.commit()
        return
    except Exception:
        logger.exception("gedcom analysis failed", extra={"import_id": str(import_id)})
        imp.status, imp.error = ImportStatus.failed, "unreadable"
        await session.commit()
        return
    people = sorted(data.persons.values(), key=lambda p: (p.year("birth") or 9999, p.display))
    imp.preview = {
        "header": data.header,
        "encoding": data.encoding,
        "counts": _counts(data),
        "warnings": _warnings(data),
        "skipped_tags": [{"tag": t, "count": n} for t, n in data.skipped_tags.most_common(30)],
        "people": [
            {
                "xref": p.xref,
                "name": p.display,
                "gender": p.gender,
                "years": _years(p.year("birth"), p.year("death")),
            }
            for p in people[:PREVIEW_PEOPLE]
        ],
        "duplicates": find_duplicates(data, await _existing_people(session, imp.tree_id)),
    }
    imp.status = ImportStatus.ready
    await session.commit()


# --- Confirm / cancel -----------------------------------------------------------------------


async def confirm(
    session: AsyncSession, imp: GedcomImport, merge: dict[str, uuid.UUID], actor: Actor
) -> GedcomImport:
    if imp.status != ImportStatus.ready:
        raise ConflictError("import_not_ready")
    known = {d["xref"] for d in (imp.preview or {}).get("duplicates", [])}
    if set(merge) - known:
        raise AppError("unknown_import_person")
    if merge:
        found = set(
            await session.scalars(
                select(Person.id).where(
                    Person.id.in_(merge.values()),
                    Person.tree_id == imp.tree_id,
                    Person.deleted_at.is_(None),
                )
            )
        )
        if set(merge.values()) - found:
            raise NotFoundError("person_not_found")
    imp.decisions = {"merge": {x: str(pid) for x, pid in merge.items()}}
    imp.status = ImportStatus.importing
    audit.record(
        session,
        actor,
        "import.confirm",
        "gedcom_import",
        imp.id,
        tree_id=imp.tree_id,
        after={"merge": len(merge)},
    )
    await session.commit()
    return imp


async def cancel(session: AsyncSession, imp: GedcomImport, actor: Actor) -> GedcomImport:
    if imp.status not in (ImportStatus.ready, ImportStatus.failed):
        raise ConflictError("import_not_ready")
    imp.status = ImportStatus.cancelled
    imp.finished_at = utcnow()
    audit.record(session, actor, "import.cancel", "gedcom_import", imp.id, tree_id=imp.tree_id)
    await session.commit()
    return imp


# --- Import -------------------------------------------------------------------------------


def _date(d: dict[str, Any] | None) -> PartialDateIn | None:
    if not d:
        return None
    try:
        return PartialDateIn(**d)
    except ValidationError:
        phrase = str(d.get("phrase") or "")[:200] or None
        return PartialDateIn(precision=DatePrecision.unknown, phrase=phrase)


class _Importer:
    def __init__(self, session: AsyncSession, imp: GedcomImport, data: GedcomData, actor: Actor):
        self.session = session
        self.imp = imp
        self.tree_id = imp.tree_id
        self.data = data
        self.actor = actor
        self.persons: dict[str, uuid.UUID] = {}
        self.places: dict[str, uuid.UUID] = {}
        self.sources: dict[str, uuid.UUID] = {}
        self.inline_sources: dict[str, uuid.UUID] = {}
        self.created: dict[str, list[str]] = {"persons": [], "sources": [], "places": []}
        self.counts: Counter[str] = Counter()
        self.warnings: list[dict[str, Any]] = []

    def warn(self, code: str, **detail: Any) -> None:
        self.counts["warnings"] += 1
        if len(self.warnings) < MAX_WARNINGS:
            self.warnings.append({"code": code, **detail})

    def who(self, xref: str | None) -> str:
        p = self.data.persons.get(xref or "")
        return p.display if p else (xref or "?")

    async def place_id(self, key: str | None) -> uuid.UUID | None:
        if not key:
            return None
        if key in self.places:
            return self.places[key]
        g = self.data.places[key]
        existing = await self.session.scalar(
            select(Place.id).where(
                Place.tree_id == self.tree_id,
                Place.deleted_at.is_(None),
                func.lower(Place.name) == g.name.lower(),
                func.coalesce(func.lower(Place.region), "") == (g.region or "").lower(),
                func.coalesce(func.lower(Place.country), "") == (g.country or "").lower(),
            )
        )
        if existing is None:
            place = await place_service.create_place(
                self.session,
                self.tree_id,
                PlaceCreate(
                    name=g.name,
                    region=g.region,
                    country=g.country,
                    latitude=g.latitude,
                    longitude=g.longitude,
                ),
                self.actor,
                commit=False,
            )
            existing = place.id
            self.created["places"].append(str(place.id))
            self.counts["places_created"] += 1
        else:
            self.counts["places_reused"] += 1
        self.places[key] = existing
        return existing

    async def source_id(self, c: GCitation) -> uuid.UUID | None:
        if c.source_xref:
            if c.source_xref in self.sources:
                return self.sources[c.source_xref]
            g = self.data.sources.get(c.source_xref)
            if g is None:
                self.warn("missing_source", xref=c.source_xref)
                return None
            body = SourceCreate(
                title=g.title,
                author=g.author,
                archive_name=g.archive_name,
                reference_number=g.reference_number,
                url=g.url,
                notes=g.notes,
            )
            cache, key = self.sources, c.source_xref
        else:
            title = c.inline_title
            if not title:
                return None
            if title in self.inline_sources:
                return self.inline_sources[title]
            body = SourceCreate(title=title)
            cache, key = self.inline_sources, title
        source = await source_service.create_source(
            self.session, self.tree_id, body, self.actor, commit=False
        )
        self.created["sources"].append(str(source.id))
        self.counts["sources"] += 1
        cache[key] = source.id
        return source.id

    async def cite(
        self, citations: list[GCitation], entity_type: str, entity_id: uuid.UUID
    ) -> None:
        for c in citations:
            source_id = await self.source_id(c)
            if source_id is None:
                continue
            try:
                async with self.session.begin_nested():
                    await source_service.create_citation(
                        self.session,
                        self.tree_id,
                        CitationCreate.model_validate(
                            {
                                "source_id": source_id,
                                "entity_type": entity_type,
                                "entity_id": entity_id,
                                "page": c.page,
                                "quality": c.quality,
                                "notes": c.notes,
                            }
                        ),
                        self.actor,
                        commit=False,
                    )
                self.counts["citations"] += 1
            except ConflictError as exc:
                if exc.code != "citation_exists":  # the same citation twice in the file
                    raise

    async def vital(self, ev: GEvent | None) -> dict[str, Any] | None:
        if ev is None:
            return None
        date = _date(ev.date)
        return {
            "date": date.model_dump() if date else None,
            "place_id": await self.place_id(ev.place),
            "description": ev.description,
        }

    async def person(self, p: GPerson) -> None:
        birth, death = p.vital("birth"), p.vital("death")
        names = [n.as_dict() for n in p.names[:50]]
        names[0]["is_primary"] = True
        body = {
            "gender": p.gender,
            "names": names,
            "birth": await self.vital(birth),
            "death": await self.vital(death),
            "biography": "\n\n".join(p.notes) or None,
            **p.attributes,
        }
        try:
            async with self.session.begin_nested():
                person = await person_service.create_person(
                    self.session,
                    self.tree_id,
                    PersonCreate.model_validate(body),
                    self.actor,
                    commit=False,
                )
        except (AppError, ValidationError) as exc:
            self.warn("person_skipped", name=p.display, reason=_reason(exc))
            return
        self.persons[p.xref] = person.id
        self.created["persons"].append(str(person.id))
        self.counts["persons_created"] += 1
        await self.cite(p.citations, "person", person.id)
        vitals = {
            e.type.value: e.id
            for e in await self.session.scalars(
                select(Event)
                .join(EventParticipant, EventParticipant.event_id == Event.id)
                .where(EventParticipant.person_id == person.id, Event.type.in_(["birth", "death"]))
            )
        }
        for ev, kind in ((birth, "birth"), (death, "death")):
            if ev is not None and kind in vitals:
                self.counts["events"] += 1
                await self.cite(ev.citations, "event", vitals[kind])
        for ev in p.events:
            if ev is birth or ev is death:
                continue
            if ev.type in ("birth", "death"):
                self.warn("extra_vital", name=p.display, type=ev.type)
                continue
            await self.event(person.id, p, ev)

    async def event(self, person_id: uuid.UUID, p: GPerson, ev: GEvent) -> None:
        date = _date(ev.date)
        try:
            async with self.session.begin_nested():
                event = await event_service.create_event(
                    self.session,
                    self.tree_id,
                    EventCreate.model_validate(
                        {
                            "type": ev.type,
                            "title": ev.title or (None if ev.type != "custom" else "Event"),
                            "description": ev.description,
                            "date": date.model_dump() if date else None,
                            "place_id": await self.place_id(ev.place),
                            "participants": [{"person_id": person_id}],
                        }
                    ),
                    self.actor,
                    commit=False,
                )
        except (AppError, ValidationError) as exc:
            self.warn("event_skipped", name=p.display, type=ev.type, reason=_reason(exc))
            return
        self.counts["events"] += 1
        await self.cite(ev.citations, "event", event.id)

    async def families(self) -> None:
        for f in self.data.families.values():
            a, b = self.persons.get(f.husband or ""), self.persons.get(f.wife or "")
            if a and b:
                await self.partnership(f, a, b)
            for child in f.children:
                child_id = self.persons.get(child.xref)
                if child_id is None:
                    continue
                pedi = (
                    next(
                        (t for fam, t in self.data.persons[child.xref].child_of if fam == f.xref),
                        None,
                    )
                    if child.xref in self.data.persons
                    else None
                )
                for parent_id, parent_xref, own in (
                    (a, f.husband, child.father_type),
                    (b, f.wife, child.mother_type),
                ):
                    if parent_id is None:
                        continue
                    kind = pedi or own or "biological"
                    try:
                        async with self.session.begin_nested():
                            await rel_service.create_parent_child(
                                self.session,
                                self.tree_id,
                                ParentChildCreate.model_validate(
                                    {"parent_id": parent_id, "child_id": child_id, "type": kind}
                                ),
                                self.actor,
                                commit=False,
                            )
                        self.counts["parent_links"] += 1
                    except AppError as exc:
                        if exc.code == "relationship_exists":  # e.g. a merged person's
                            self.counts["links_existing"] += 1
                            continue
                        self.warn(
                            "link_skipped",
                            parent=self.who(parent_xref),
                            child=self.who(child.xref),
                            reason=_reason(exc),
                        )

    async def partnership(self, f: Any, a: uuid.UUID, b: uuid.UUID) -> None:
        exists = await self.session.scalar(
            select(Partnership.id).where(
                Partnership.deleted_at.is_(None),
                or_(
                    and_(Partnership.person_a_id == a, Partnership.person_b_id == b),
                    and_(Partnership.person_a_id == b, Partnership.person_b_id == a),
                ),
            )
        )
        if exists:
            self.counts["partnerships_existing"] += 1
            return
        start, end = _date(f.start_date), _date(f.end_date)
        try:
            async with self.session.begin_nested():
                p = await rel_service.create_partnership(
                    self.session,
                    self.tree_id,
                    PartnershipCreate.model_validate(
                        {
                            "person_a_id": a,
                            "person_b_id": b,
                            "type": "marriage" if f.married else "partnership",
                            "start_date": start.model_dump() if start else None,
                            "end_date": end.model_dump() if end else None,
                            "end_reason": f.end_reason,
                            "place_id": await self.place_id(f.place),
                            "notes": "\n\n".join(f.notes) or None,
                        }
                    ),
                    self.actor,
                    commit=False,
                )
        except (AppError, ValidationError) as exc:
            self.warn(
                "partnership_skipped",
                a=self.who(f.husband),
                b=self.who(f.wife),
                reason=_reason(exc),
            )
            return
        self.counts["partnerships"] += 1
        await self.cite(f.citations, "partnership", p.id)

    async def run(self, merge: dict[str, str]) -> None:
        for xref, person_id in merge.items():
            if xref in self.data.persons:
                self.persons[xref] = uuid.UUID(person_id)
                self.counts["persons_merged"] += 1
        for p in self.data.persons.values():
            if p.xref not in self.persons:
                await self.person(p)
        await self.families()


def _reason(exc: Exception) -> str:
    if isinstance(exc, AppError):
        return exc.code
    if isinstance(exc, ValidationError):
        return "validation_error"
    return "error"


async def apply(session: AsyncSession, storage: Storage, import_id: uuid.UUID) -> None:
    """Import everything in one transaction; on an unexpected error nothing is kept."""
    imp = await session.get(GedcomImport, import_id)
    if imp is None or imp.status != ImportStatus.importing:
        return
    user = await session.get(User, imp.created_by_id) if imp.created_by_id else None
    actor = Actor(user, ip="gedcom-import")
    merge = dict((imp.decisions or {}).get("merge", {}))
    try:
        data = await _load(storage, imp)
        importer = _Importer(session, imp, data, actor)
        await importer.run(merge)
        imp.result = {
            "counts": dict(importer.counts),
            "warnings": importer.warnings,
            "created": importer.created,
        }
        imp.status = ImportStatus.done
        imp.finished_at = utcnow()
        audit.record(
            session,
            actor,
            "import.apply",
            "gedcom_import",
            imp.id,
            tree_id=imp.tree_id,
            after=dict(importer.counts),
        )
        await session.commit()
    except Exception as exc:
        logger.exception("gedcom import failed", extra={"import_id": str(import_id)})
        await session.rollback()
        imp = await session.get(GedcomImport, import_id)
        assert imp is not None
        imp.status = ImportStatus.failed
        imp.error = _reason(exc) if isinstance(exc, AppError | ValidationError) else "import_failed"
        imp.finished_at = utcnow()
        await session.commit()


# --- Undo ---------------------------------------------------------------------------------


async def start_undo(session: AsyncSession, imp: GedcomImport, actor: Actor) -> GedcomImport:
    if imp.status != ImportStatus.done:
        raise ConflictError("import_not_done")
    imp.status = ImportStatus.undoing
    audit.record(session, actor, "import.undo", "gedcom_import", imp.id, tree_id=imp.tree_id)
    await session.commit()
    return imp


async def undo(session: AsyncSession, import_id: uuid.UUID) -> None:
    """Move every person and source the import created to the trash (people take their
    events and relationships with them, so it can all be restored from the trash)."""
    imp = await session.get(GedcomImport, import_id)
    if imp is None or imp.status != ImportStatus.undoing:
        return
    user = await session.get(User, imp.created_by_id) if imp.created_by_id else None
    actor = Actor(user, ip="gedcom-import")
    created = (imp.result or {}).get("created", {})
    ids = [uuid.UUID(x) for x in created.get("persons", [])]
    for person in await session.scalars(
        select(Person).where(Person.id.in_(ids), Person.deleted_at.is_(None))
    ):
        await trash.delete_person(session, person, actor)
    source_ids = [uuid.UUID(x) for x in created.get("sources", [])]
    for source in await session.scalars(
        select(Source).where(Source.id.in_(source_ids), Source.deleted_at.is_(None))
    ):
        await source_service.delete_source(session, source, actor)
    imp = await session.get(GedcomImport, import_id)
    assert imp is not None
    imp.status = ImportStatus.undone
    imp.finished_at = utcnow()
    await session.commit()
