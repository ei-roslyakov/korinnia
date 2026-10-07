"""Audit trail: every change is recorded with before/after snapshots (JSONB)."""

from __future__ import annotations

import enum
import uuid
from collections.abc import Iterable
from datetime import date, datetime
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog
from app.schemas.audit import AuditQuery
from app.services.context import Actor

# Never written to the audit log.
SECRET_FIELDS = frozenset({"password_hash", "totp_secret", "token_hash", "code_hash"})


def _jsonable(value: Any) -> Any:
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, enum.Enum):
        return value.value
    return value


def snapshot(obj: Any, fields: Iterable[str]) -> dict[str, Any]:
    """Serialisable dict of selected attributes, excluding secrets."""
    return {f: _jsonable(getattr(obj, f)) for f in fields if f not in SECRET_FIELDS}


def diff_only(
    before: dict[str, Any], after: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    changed = {k for k in before.keys() | after.keys() if before.get(k) != after.get(k)}
    return (
        {k: v for k, v in before.items() if k in changed},
        {k: v for k, v in after.items() if k in changed},
    )


def record(
    session: AsyncSession,
    actor: Actor,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID | None = None,
    *,
    tree_id: uuid.UUID | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> AuditLog:
    entry = AuditLog(
        user_id=actor.user.id if actor.user else None,
        user_label=actor.label,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        tree_id=tree_id,
        before=before,
        after=after,
        ip_address=actor.ip,
    )
    session.add(entry)
    return entry


def _filtered(stmt: Select[Any], q: AuditQuery) -> Select[Any]:
    if q.user_id:
        stmt = stmt.where(AuditLog.user_id == q.user_id)
    if q.action:
        stmt = stmt.where(AuditLog.action == q.action)
    if q.entity_type:
        stmt = stmt.where(AuditLog.entity_type == q.entity_type)
    if q.entity_id:
        stmt = stmt.where(AuditLog.entity_id == q.entity_id)
    if q.tree_id:
        stmt = stmt.where(AuditLog.tree_id == q.tree_id)
    if q.date_from:
        stmt = stmt.where(AuditLog.created_at >= q.date_from)
    if q.date_to:
        stmt = stmt.where(AuditLog.created_at <= q.date_to)
    return stmt


async def list_entries(
    session: AsyncSession, q: AuditQuery, *, limit: int, offset: int
) -> tuple[list[AuditLog], int]:
    total = await session.scalar(_filtered(select(func.count()).select_from(AuditLog), q))
    rows = await session.scalars(
        _filtered(select(AuditLog), q)
        .order_by(AuditLog.created_at.desc(), AuditLog.id)
        .limit(limit)
        .offset(offset)
    )
    return list(rows), total or 0


async def list_actions(session: AsyncSession) -> list[str]:
    rows = await session.scalars(select(AuditLog.action).distinct().order_by(AuditLog.action))
    return list(rows)
