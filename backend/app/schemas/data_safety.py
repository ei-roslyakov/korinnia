"""Integrity checks and GEDCOM imports (phase 9)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.core.enums import ImportStatus, IntegrityProblem, IntegrityStatus


class IntegrityRunOut(BaseModel):
    id: uuid.UUID
    status: IntegrityStatus
    trigger: str
    triggered_by: str | None
    started_at: datetime
    finished_at: datetime | None
    files_checked: int
    bytes_checked: int
    problems: int
    untracked_files: int
    error: str | None


class IntegrityIssueOut(BaseModel):
    key: str
    problem: IntegrityProblem
    media_id: uuid.UUID | None
    tree_id: uuid.UUID | None
    tree_name: str | None
    filename: str | None
    expected_size: int | None
    actual_size: int | None
    expected_sha256: str | None
    actual_sha256: str | None


class IntegrityOverview(BaseModel):
    # Originals currently recorded (what a full run will check).
    total_files: int
    total_bytes: int
    runs: list[IntegrityRunOut]
    # Problems found by the latest finished run.
    issues: list[IntegrityIssueOut]


class GedcomImportOut(BaseModel):
    id: uuid.UUID
    status: ImportStatus
    filename: str
    size: int
    created_at: datetime
    finished_at: datetime | None
    created_by: str | None
    preview: dict[str, Any] | None
    result: dict[str, Any] | None
    error: str | None


class GedcomConfirm(BaseModel):
    """{GEDCOM xref (e.g. "@I12@"): id of the existing person it is the same as}. People not
    listed are created new."""

    merge: dict[str, uuid.UUID] = {}
