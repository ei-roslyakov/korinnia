"""GEDCOM imports and integrity checks of stored originals (phase 9)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import ImportStatus, IntegrityProblem, IntegrityStatus
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, text_enum, utcnow_column


class GedcomImport(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One uploaded GEDCOM file: its analysis (preview), the user's choices and the result.

    The file itself is kept in storage under `file_key` so the import can be re-read when
    confirmed and traced back later.
    """

    __tablename__ = "gedcom_imports"

    tree_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("trees.id", ondelete="CASCADE"), index=True
    )
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    status: Mapped[ImportStatus] = mapped_column(
        text_enum(ImportStatus, "import_status"), default=ImportStatus.analyzing
    )
    file_key: Mapped[str] = mapped_column(String(500))
    filename: Mapped[str] = mapped_column(String(500))
    size: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64))
    # Counts, warnings, people list and duplicate candidates (see services/gedcom).
    preview: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    # {gedcom xref: existing person id} for people the user chose to merge.
    decisions: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    # Counts and the ids of everything created (used by "undo import").
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class IntegrityRun(UUIDPrimaryKeyMixin, Base):
    """One pass over every stored original, re-computing its SHA-256."""

    __tablename__ = "integrity_runs"

    status: Mapped[IntegrityStatus] = mapped_column(
        text_enum(IntegrityStatus, "integrity_status"), default=IntegrityStatus.running
    )
    # "scheduled" or "manual"; who started a manual run.
    trigger: Mapped[str] = mapped_column(String(20))
    triggered_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    started_at: Mapped[datetime] = utcnow_column()
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    files_checked: Mapped[int] = mapped_column(Integer, default=0)
    bytes_checked: Mapped[int] = mapped_column(BigInteger, default=0)
    problems: Mapped[int] = mapped_column(Integer, default=0)
    # Files under originals/ that no media record points at (informational).
    untracked_files: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)


class IntegrityIssue(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "integrity_issues"

    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("integrity_runs.id", ondelete="CASCADE"), index=True
    )
    media_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("media_files.id", ondelete="SET NULL")
    )
    tree_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("trees.id", ondelete="SET NULL"))
    key: Mapped[str] = mapped_column(String(500))
    problem: Mapped[IntegrityProblem] = mapped_column(
        text_enum(IntegrityProblem, "integrity_problem")
    )
    expected_size: Mapped[int | None] = mapped_column(BigInteger)
    actual_size: Mapped[int | None] = mapped_column(BigInteger)
    expected_sha256: Mapped[str | None] = mapped_column(String(64))
    actual_sha256: Mapped[str | None] = mapped_column(String(64))
