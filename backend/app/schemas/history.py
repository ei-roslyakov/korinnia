from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

TrashEntityType = Literal["person", "place", "event", "parent_child", "partnership"]


class TrashItem(BaseModel):
    entity_type: TrashEntityType
    entity_id: uuid.UUID
    label: str
    deleted_at: datetime
    deleted_by: str | None
    batch_size: int
