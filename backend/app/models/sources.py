"""Sources and citations: where each fact comes from."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import CitationQuality, CitedEntity, SourceType
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, text_enum
from app.models.genealogy_base import AuthoredMixin, SoftDeleteMixin, TreeScopedMixin


class Source(
    UUIDPrimaryKeyMixin, TreeScopedMixin, AuthoredMixin, SoftDeleteMixin, TimestampMixin, Base
):
    __tablename__ = "sources"
    __table_args__ = (
        Index(
            "ix_sources_search_text_trgm",
            "search_text",
            postgresql_using="gin",
            postgresql_ops={"search_text": "gin_trgm_ops"},
        ),
    )

    title: Mapped[str] = mapped_column(String(500))
    type: Mapped[SourceType] = mapped_column(text_enum(SourceType, "source_type"))
    author: Mapped[str | None] = mapped_column(String(300))
    archive_name: Mapped[str | None] = mapped_column(String(300))
    # Archival signature, e.g. "ДАІФО, ф. 631, оп. 1, спр. 12, арк. 34".
    reference_number: Mapped[str | None] = mapped_column(String(300))
    url: Mapped[str | None] = mapped_column(String(2000))
    notes: Mapped[str | None] = mapped_column(Text)
    # Title / author / archive / reference, normalised + transliterated (see search_text.py).
    search_text: Mapped[str] = mapped_column(Text, default="", server_default="")


class SourceMedia(Base):
    """Scans / photos of a source (e.g. the page of a parish register)."""

    __tablename__ = "source_media"

    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"), primary_key=True
    )
    media_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("media_files.id", ondelete="CASCADE"), primary_key=True
    )


class Citation(
    UUIDPrimaryKeyMixin, TreeScopedMixin, AuthoredMixin, SoftDeleteMixin, TimestampMixin, Base
):
    """A source supporting a fact: a person (optionally one `field`), a name, an event, a
    relationship or a media item. No FK on `entity_id` (polymorphic) — validated in code."""

    __tablename__ = "citations"
    # Duplicates (same source, fact, field and page) are rejected by the service; a DB
    # unique constraint would break re-adding a soft-deleted citation.
    __table_args__ = (Index("ix_citations_entity", "entity_type", "entity_id"),)

    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"), index=True
    )
    entity_type: Mapped[CitedEntity] = mapped_column(text_enum(CitedEntity, "cited_entity"))
    entity_id: Mapped[uuid.UUID] = mapped_column()
    field: Mapped[str | None] = mapped_column(String(100))
    page: Mapped[str | None] = mapped_column(String(300))
    quality: Mapped[CitationQuality] = mapped_column(
        text_enum(CitationQuality, "citation_quality"), default=CitationQuality.unverified
    )
    notes: Mapped[str | None] = mapped_column(Text)
