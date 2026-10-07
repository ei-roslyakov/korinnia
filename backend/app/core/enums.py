"""Enumerations shared by models, schemas and domain logic.

No app imports, so it is safe to import from anywhere. In the database they are stored as
text + CHECK constraint (not native PG enums: easier to evolve).
"""

from __future__ import annotations

from enum import StrEnum


class TreeRole(StrEnum):
    viewer = "viewer"
    contributor = "contributor"
    editor = "editor"
    admin = "admin"

    @property
    def rank(self) -> int:
        return _ROLE_RANK[self]

    def at_least(self, other: TreeRole) -> bool:
        return self.rank >= other.rank


_ROLE_RANK = {
    TreeRole.viewer: 10,
    TreeRole.contributor: 20,
    TreeRole.editor: 30,
    TreeRole.admin: 40,
}


class Language(StrEnum):
    uk = "uk"
    en = "en"
    pl = "pl"


# --- Genealogy ----------------------------------------------------------------------------


class Gender(StrEnum):
    male = "male"
    female = "female"
    other = "other"
    unknown = "unknown"


class ResearchStatus(StrEnum):
    complete = "complete"
    partial = "partial"
    unknown = "unknown"


class NameType(StrEnum):
    birth = "birth"
    married = "married"
    nickname = "nickname"
    alias = "alias"
    religious = "religious"
    other = "other"


class Script(StrEnum):
    cyrillic = "cyrillic"
    latin = "latin"
    other = "other"


class EventType(StrEnum):
    birth = "birth"
    baptism = "baptism"
    death = "death"
    burial = "burial"
    marriage = "marriage"
    divorce = "divorce"
    education = "education"
    graduation = "graduation"
    military_service = "military_service"
    occupation = "occupation"
    residence = "residence"
    emigration = "emigration"
    immigration = "immigration"
    award = "award"
    illness = "illness"
    custom = "custom"


class ParticipantRole(StrEnum):
    principal = "principal"
    spouse = "spouse"
    witness = "witness"
    godparent = "godparent"
    officiant = "officiant"
    other = "other"


class DatePrecision(StrEnum):
    exact = "exact"
    month = "month"
    year = "year"
    approx = "approx"
    before = "before"
    after = "after"
    between = "between"
    unknown = "unknown"


class ParentChildType(StrEnum):
    biological = "biological"
    adoptive = "adoptive"
    step = "step"
    foster = "foster"
    unknown = "unknown"


class PartnershipType(StrEnum):
    marriage = "marriage"
    civil_union = "civil_union"
    partnership = "partnership"


class PartnershipEndReason(StrEnum):
    divorce = "divorce"
    death = "death"
    separation = "separation"
    other = "other"


# --- Media --------------------------------------------------------------------------------


class MediaKind(StrEnum):
    photo = "photo"
    document_scan = "document_scan"
    audio = "audio"
    video = "video"
    pdf = "pdf"
    other = "other"


class ProcessingStatus(StrEnum):
    pending = "pending"
    ready = "ready"
    failed = "failed"
