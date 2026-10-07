from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.schemas.common import Schema


class AuditEntryOut(Schema):
    id: uuid.UUID
    created_at: datetime
    user_id: uuid.UUID | None
    user_label: str | None
    action: str
    entity_type: str
    entity_id: uuid.UUID | None
    tree_id: uuid.UUID | None
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    ip_address: str | None


class AuditQuery(BaseModel):
    user_id: uuid.UUID | None = None
    action: str | None = None
    entity_type: str | None = None
    entity_id: uuid.UUID | None = None
    tree_id: uuid.UUID | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
