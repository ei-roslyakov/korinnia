"""ORM models. Import every model module here so Alembic autogenerate sees it."""

from app.core.enums import (
    CitationQuality,
    CitedEntity,
    CommentTarget,
    DatePrecision,
    EventType,
    Gender,
    Language,
    MediaKind,
    NameType,
    ParentChildType,
    ParticipantRole,
    PartnershipEndReason,
    PartnershipType,
    ProcessingStatus,
    QuestionStatus,
    ResearchStatus,
    Script,
    SourceType,
    StoryStatus,
    SuggestionStatus,
    SuggestionTarget,
    TreeRole,
)
from app.models.audit import AuditLog
from app.models.base import Base
from app.models.collaboration import Comment, EditSuggestion, OpenQuestion
from app.models.data_safety import GedcomImport, IntegrityIssue, IntegrityRun
from app.models.event import Event, EventParticipant
from app.models.invitation import Invitation, PasswordResetToken
from app.models.layout import LayoutOffset
from app.models.media import MediaFile, MediaPerson
from app.models.person import Person, PersonName
from app.models.place import Place
from app.models.relationship import ParentChild, Partnership
from app.models.sources import Citation, Source, SourceMedia
from app.models.stories import Story, StoryMedia, StoryPerson
from app.models.tree import Tree, TreeMembership
from app.models.user import LoginAttempt, RecoveryCode, RefreshToken, User

__all__ = [
    "AuditLog",
    "Base",
    "Citation",
    "CitationQuality",
    "CitedEntity",
    "Comment",
    "CommentTarget",
    "DatePrecision",
    "EditSuggestion",
    "Event",
    "EventParticipant",
    "EventType",
    "GedcomImport",
    "Gender",
    "IntegrityIssue",
    "IntegrityRun",
    "Invitation",
    "Language",
    "LayoutOffset",
    "LoginAttempt",
    "MediaFile",
    "MediaKind",
    "MediaPerson",
    "NameType",
    "OpenQuestion",
    "ParentChild",
    "ParentChildType",
    "ParticipantRole",
    "Partnership",
    "PartnershipEndReason",
    "PartnershipType",
    "PasswordResetToken",
    "Person",
    "PersonName",
    "Place",
    "ProcessingStatus",
    "QuestionStatus",
    "RecoveryCode",
    "RefreshToken",
    "ResearchStatus",
    "Script",
    "Source",
    "SourceMedia",
    "SourceType",
    "Story",
    "StoryMedia",
    "StoryPerson",
    "StoryStatus",
    "SuggestionStatus",
    "SuggestionTarget",
    "Tree",
    "TreeMembership",
    "TreeRole",
    "User",
]
