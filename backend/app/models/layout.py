"""Per-tree manual adjustments of the automatic canvas layout (presentation only)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class LayoutOffset(Base):
    """Offset of a person card from its ELK-computed position. Offsets (not absolute
    coordinates) keep working in focus mode and when the automatic layout changes."""

    __tablename__ = "layout_offsets"

    tree_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("trees.id", ondelete="CASCADE"), primary_key=True
    )
    person_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("persons.id", ondelete="CASCADE"), primary_key=True
    )
    dx: Mapped[float] = mapped_column(Float)
    dy: Mapped[float] = mapped_column(Float)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
