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


class LivingPrivacy(StrEnum):
    """Who sees only the basics of living people (D114)."""

    off = "off"
    share_links = "share_links"
    viewers_and_share_links = "viewers_and_share_links"


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


# --- Sources, stories, collaboration ------------------------------------------------------


class SourceType(StrEnum):
    civil_record = "civil_record"
    church_record = "church_record"
    archive_document = "archive_document"
    census = "census"
    newspaper = "newspaper"
    letter = "letter"
    oral_history = "oral_history"
    book = "book"
    website = "website"
    other = "other"


class CitationQuality(StrEnum):
    primary = "primary"
    secondary = "secondary"
    family_tradition = "family_tradition"
    unverified = "unverified"


class CitedEntity(StrEnum):
    """What a citation supports."""

    person = "person"
    person_name = "person_name"
    event = "event"
    parent_child = "parent_child"
    partnership = "partnership"
    media = "media"


class StoryKind(StrEnum):
    story = "story"
    recipe = "recipe"
    tradition = "tradition"


class StoryStatus(StrEnum):
    draft = "draft"
    pending_review = "pending_review"
    published = "published"


class SuggestionStatus(StrEnum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class SuggestionTarget(StrEnum):
    person = "person"
    event = "event"


class CommentTarget(StrEnum):
    person = "person"
    story = "story"
    media = "media"


class QuestionStatus(StrEnum):
    open = "open"
    resolved = "resolved"


# --- Data safety (phase 9) ----------------------------------------------------------------


class ImportStatus(StrEnum):
    """GEDCOM import lifecycle: analyzing → ready → importing → done (→ undoing → undone)."""

    analyzing = "analyzing"
    ready = "ready"
    importing = "importing"
    done = "done"
    failed = "failed"
    undoing = "undoing"
    undone = "undone"
    cancelled = "cancelled"


class IntegrityStatus(StrEnum):
    running = "running"
    done = "done"
    failed = "failed"


class IntegrityProblem(StrEnum):
    missing = "missing"
    size_mismatch = "size_mismatch"
    hash_mismatch = "hash_mismatch"
    unreadable = "unreadable"
