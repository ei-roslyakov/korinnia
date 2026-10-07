"""Full JSON snapshots of genealogical entities, stored in the audit log (before/after).

Snapshots make every change reviewable and any earlier version restorable. They are plain
JSON with stable keys, so they also document the data for future readers.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Event,
    EventParticipant,
    EventType,
    Gender,
    NameType,
    ParentChild,
    ParentChildType,
    ParticipantRole,
    Partnership,
    PartnershipEndReason,
    PartnershipType,
    Person,
    PersonName,
    Place,
    ResearchStatus,
    Script,
)
from app.services.genealogy.common import date_from_dict, date_to_dict, set_date
from app.services.genealogy.vitals import Vitals, set_vital
from app.services.search_text import build_search_text

PERSON_FIELDS = (
    "gender",
    "is_living",
    "short_summary",
    "biography",
    "occupation",
    "education",
    "religion",
    "nationality",
    "notes_for_descendants",
    "research_status",
    "primary_photo_id",
    "primary_photo_crop",
)
NAME_FIELDS = (
    "type",
    "first_name",
    "middle_name",
    "patronymic",
    "last_name",
    "maiden_name",
    "script",
    "is_primary",
    "notes",
)
PLACE_FIELDS = ("name", "historical_names", "country", "region", "latitude", "longitude", "notes")


def _plain(value: Any) -> Any:
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, Decimal):
        return str(value)
    if hasattr(value, "value"):  # enum
        return value.value
    return value


def _vital(ev: Event | None) -> dict[str, Any] | None:
    if ev is None:
        return None
    return {
        "date": date_to_dict(ev.date),
        "place_id": _plain(ev.place_id),
        "description": ev.description,
    }


def person_snapshot(person: Person, names: list[PersonName], vitals: Vitals) -> dict[str, Any]:
    return {
        **{f: _plain(getattr(person, f)) for f in PERSON_FIELDS},
        "names": [
            {f: _plain(getattr(n, f)) for f in NAME_FIELDS}
            for n in sorted(names, key=lambda n: n.sort_order)
        ],
        "birth": _vital(vitals.birth),
        "death": _vital(vitals.death),
    }


def make_names(person: Person, names: list[dict[str, Any]]) -> list[PersonName]:
    """Build PersonName rows; ensures exactly one primary name if any exist."""
    rows = []
    has_primary = any(n.get("is_primary") for n in names)
    for i, data in enumerate(names):
        name = PersonName(
            person_id=person.id,
            type=NameType(data.get("type") or NameType.birth),
            first_name=data.get("first_name"),
            middle_name=data.get("middle_name"),
            patronymic=data.get("patronymic"),
            last_name=data.get("last_name"),
            maiden_name=data.get("maiden_name"),
            script=Script(data.get("script") or Script.cyrillic),
            is_primary=bool(data.get("is_primary")) or (not has_primary and i == 0),
            sort_order=i,
            notes=data.get("notes"),
        )
        name.search_text = build_search_text(
            [name.first_name, name.middle_name, name.patronymic, name.last_name, name.maiden_name]
        )
        rows.append(name)
    return rows


async def apply_person_snapshot(
    session: AsyncSession, person: Person, snap: dict[str, Any], user_id: uuid.UUID | None
) -> None:
    person.gender = Gender(snap["gender"])
    person.research_status = ResearchStatus(snap["research_status"])
    for f in PERSON_FIELDS:
        if f not in ("gender", "research_status", "primary_photo_id"):
            setattr(person, f, snap.get(f))
    photo = snap.get("primary_photo_id")
    person.primary_photo_id = uuid.UUID(photo) if photo else None
    person.avatar_key = None  # regenerated from the restored photo choice
    person.updated_by_id = user_id
    await session.refresh(person, ["names"])
    person.names = make_names(person, snap.get("names", []))
    for key, etype in (("birth", EventType.birth), ("death", EventType.death)):
        vital = snap.get(key)
        await set_vital(
            session,
            person,
            etype,
            date=date_from_dict(vital.get("date")) if vital else None,
            place_id=uuid.UUID(vital["place_id"]) if vital and vital.get("place_id") else None,
            description=vital.get("description") if vital else None,
            remove=vital is None,
            user_id=user_id,
        )


def event_snapshot(event: Event) -> dict[str, Any]:
    return {
        "type": event.type.value,
        "title": event.title,
        "description": event.description,
        "date": date_to_dict(event.date),
        "place_id": _plain(event.place_id),
        "cemetery_name": event.cemetery_name,
        "burial_plot": event.burial_plot,
        "latitude": _plain(event.latitude),
        "longitude": _plain(event.longitude),
        "participants": [
            {"person_id": str(p.person_id), "role": p.role.value}
            for p in sorted(event.participants, key=lambda p: str(p.person_id))
        ],
    }


def set_participants(event: Event, wanted: list[tuple[uuid.UUID, ParticipantRole]]) -> None:
    """Sync participants in place. Replacing the list wholesale would INSERT new rows before
    DELETEing old ones and violate the (event_id, person_id) unique constraint."""
    roles = dict(wanted)
    existing = {p.person_id: p for p in event.participants}
    for person_id, participant in existing.items():
        if person_id in roles:
            participant.role = roles[person_id]
        else:
            event.participants.remove(participant)
    for person_id, role in wanted:
        if person_id not in existing:
            event.participants.append(EventParticipant(person_id=person_id, role=role))


def apply_event_snapshot(event: Event, snap: dict[str, Any], user_id: uuid.UUID | None) -> None:
    event.type = EventType(snap["type"])
    event.title = snap.get("title")
    event.description = snap.get("description")
    set_date(event, "date", "date_sort", date_from_dict(snap.get("date")))
    event.place_id = uuid.UUID(snap["place_id"]) if snap.get("place_id") else None
    event.cemetery_name = snap.get("cemetery_name")
    event.burial_plot = snap.get("burial_plot")
    event.latitude = Decimal(snap["latitude"]) if snap.get("latitude") else None
    event.longitude = Decimal(snap["longitude"]) if snap.get("longitude") else None
    set_participants(
        event,
        [
            (uuid.UUID(p["person_id"]), ParticipantRole(p["role"]))
            for p in snap.get("participants", [])
        ],
    )
    event.updated_by_id = user_id


def parent_child_snapshot(link: ParentChild) -> dict[str, Any]:
    return {
        "parent_id": str(link.parent_id),
        "child_id": str(link.child_id),
        "type": link.type.value,
        "notes": link.notes,
    }


def apply_parent_child_snapshot(link: ParentChild, snap: dict[str, Any]) -> None:
    link.type = ParentChildType(snap["type"])
    link.notes = snap.get("notes")


def partnership_snapshot(p: Partnership) -> dict[str, Any]:
    return {
        "person_a_id": str(p.person_a_id),
        "person_b_id": str(p.person_b_id),
        "type": p.type.value,
        "start_date": date_to_dict(p.start_date),
        "end_date": date_to_dict(p.end_date),
        "end_reason": _plain(p.end_reason),
        "place_id": _plain(p.place_id),
        "notes": p.notes,
    }


def apply_partnership_snapshot(p: Partnership, snap: dict[str, Any]) -> None:
    p.type = PartnershipType(snap["type"])
    set_date(p, "start_date", "start_sort", date_from_dict(snap.get("start_date")))
    set_date(p, "end_date", "end_sort", date_from_dict(snap.get("end_date")))
    p.end_reason = PartnershipEndReason(snap["end_reason"]) if snap.get("end_reason") else None
    p.place_id = uuid.UUID(snap["place_id"]) if snap.get("place_id") else None
    p.notes = snap.get("notes")


def place_snapshot(place: Place) -> dict[str, Any]:
    return {f: _plain(getattr(place, f)) for f in PLACE_FIELDS}


def place_search_text(place: Place) -> str:
    return build_search_text(
        [place.name, place.region, place.country]
        + [h.get("name") for h in place.historical_names or []]
    )


def apply_place_snapshot(place: Place, snap: dict[str, Any]) -> None:
    for f in PLACE_FIELDS:
        value = snap.get(f)
        if f in ("latitude", "longitude") and value is not None:
            value = Decimal(value)
        setattr(place, f, value if value is not None or f != "historical_names" else [])
    place.search_text = place_search_text(place)
