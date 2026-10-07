"""ORM models. Import every model module here so Alembic autogenerate sees it."""

from app.core.enums import (
    DatePrecision,
    EventType,
    Gender,
    Language,
    NameType,
    ParentChildType,
    ParticipantRole,
    PartnershipEndReason,
    PartnershipType,
    ResearchStatus,
    Script,
    TreeRole,
)
from app.models.audit import AuditLog
from app.models.base import Base
from app.models.event import Event, EventParticipant
from app.models.invitation import Invitation, PasswordResetToken
from app.models.layout import LayoutOffset
from app.models.person import Person, PersonName
from app.models.place import Place
from app.models.relationship import ParentChild, Partnership
from app.models.tree import Tree, TreeMembership
from app.models.user import LoginAttempt, RecoveryCode, RefreshToken, User

__all__ = [
    "AuditLog",
    "Base",
    "DatePrecision",
    "Event",
    "EventParticipant",
    "EventType",
    "Gender",
    "Invitation",
    "Language",
    "LayoutOffset",
    "LoginAttempt",
    "NameType",
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
    "RecoveryCode",
    "RefreshToken",
    "ResearchStatus",
    "Script",
    "Tree",
    "TreeMembership",
    "TreeRole",
    "User",
]
