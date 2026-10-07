"""Media files, media-person links (face regions), person primary photo + avatar.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-07 08:31:15.300064+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "media_files",
        sa.Column(
            "kind",
            sa.Enum(
                "photo",
                "document_scan",
                "audio",
                "video",
                "pdf",
                "other",
                name="media_kind",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("original_key", sa.String(length=500), nullable=False),
        sa.Column("original_filename", sa.String(length=500), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("size", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("web_key", sa.String(length=500), nullable=True),
        sa.Column("thumb_key", sa.String(length=500), nullable=True),
        sa.Column(
            "processing_status",
            sa.Enum(
                "pending",
                "ready",
                "failed",
                name="processing_status",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("processing_error", sa.Text(), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("title", sa.String(length=300), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("date_year", sa.Integer(), nullable=True),
        sa.Column("date_month", sa.SmallInteger(), nullable=True),
        sa.Column("date_day", sa.SmallInteger(), nullable=True),
        sa.Column(
            "date_precision",
            sa.Enum(
                "exact",
                "month",
                "year",
                "approx",
                "before",
                "after",
                "between",
                "unknown",
                name="date_precision",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=True,
        ),
        sa.Column("date_end_year", sa.Integer(), nullable=True),
        sa.Column("date_end_month", sa.SmallInteger(), nullable=True),
        sa.Column("date_end_day", sa.SmallInteger(), nullable=True),
        sa.Column("date_phrase", sa.String(length=200), nullable=True),
        sa.Column("date_sort", sa.Date(), nullable=True),
        sa.Column("place_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tree_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column("updated_by_id", sa.Uuid(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_batch_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name=op.f("fk_media_files_created_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["place_id"],
            ["places.id"],
            name=op.f("fk_media_files_place_id_places"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tree_id"], ["trees.id"], name=op.f("fk_media_files_tree_id_trees"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_id"],
            ["users.id"],
            name=op.f("fk_media_files_updated_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_media_files")),
    )
    op.create_index(op.f("ix_media_files_date_sort"), "media_files", ["date_sort"], unique=False)
    op.create_index(op.f("ix_media_files_deleted_at"), "media_files", ["deleted_at"], unique=False)
    op.create_index(
        op.f("ix_media_files_deleted_batch_id"), "media_files", ["deleted_batch_id"], unique=False
    )
    op.create_index(op.f("ix_media_files_kind"), "media_files", ["kind"], unique=False)
    op.create_index(op.f("ix_media_files_place_id"), "media_files", ["place_id"], unique=False)
    op.create_index(op.f("ix_media_files_sha256"), "media_files", ["sha256"], unique=False)
    op.create_index(op.f("ix_media_files_tree_id"), "media_files", ["tree_id"], unique=False)
    op.create_table(
        "media_persons",
        sa.Column("media_id", sa.Uuid(), nullable=False),
        sa.Column("person_id", sa.Uuid(), nullable=False),
        sa.Column("region", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["media_id"],
            ["media_files.id"],
            name=op.f("fk_media_persons_media_id_media_files"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["person_id"],
            ["persons.id"],
            name=op.f("fk_media_persons_person_id_persons"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_media_persons")),
        sa.UniqueConstraint(
            "media_id", "person_id", name=op.f("uq_media_persons_media_id_person_id")
        ),
    )
    op.create_index(op.f("ix_media_persons_media_id"), "media_persons", ["media_id"], unique=False)
    op.create_index(
        op.f("ix_media_persons_person_id"), "media_persons", ["person_id"], unique=False
    )
    op.add_column(
        "persons",
        sa.Column("primary_photo_crop", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column("persons", sa.Column("avatar_key", sa.String(length=500), nullable=True))
    op.create_foreign_key(
        op.f("fk_persons_primary_photo_id_media_files"),
        "persons",
        "media_files",
        ["primary_photo_id"],
        ["id"],
        ondelete="SET NULL",
        use_alter=True,
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_persons_primary_photo_id_media_files"), "persons", type_="foreignkey"
    )
    op.drop_column("persons", "avatar_key")
    op.drop_column("persons", "primary_photo_crop")
    op.drop_index(op.f("ix_media_persons_person_id"), table_name="media_persons")
    op.drop_index(op.f("ix_media_persons_media_id"), table_name="media_persons")
    op.drop_table("media_persons")
    op.drop_index(op.f("ix_media_files_tree_id"), table_name="media_files")
    op.drop_index(op.f("ix_media_files_sha256"), table_name="media_files")
    op.drop_index(op.f("ix_media_files_place_id"), table_name="media_files")
    op.drop_index(op.f("ix_media_files_kind"), table_name="media_files")
    op.drop_index(op.f("ix_media_files_deleted_batch_id"), table_name="media_files")
    op.drop_index(op.f("ix_media_files_deleted_at"), table_name="media_files")
    op.drop_index(op.f("ix_media_files_date_sort"), table_name="media_files")
    op.drop_table("media_files")
