"""GEDCOM imports and integrity checks of stored originals (phase 9).

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-08 10:15:37.580793+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "integrity_runs",
        sa.Column(
            "status",
            sa.Enum(
                "running",
                "done",
                "failed",
                name="integrity_status",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("trigger", sa.String(length=20), nullable=False),
        sa.Column("triggered_by_id", sa.Uuid(), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("files_checked", sa.Integer(), nullable=False),
        sa.Column("bytes_checked", sa.BigInteger(), nullable=False),
        sa.Column("problems", sa.Integer(), nullable=False),
        sa.Column("untracked_files", sa.Integer(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["triggered_by_id"],
            ["users.id"],
            name=op.f("fk_integrity_runs_triggered_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_integrity_runs")),
    )
    op.create_table(
        "gedcom_imports",
        sa.Column("tree_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "analyzing",
                "ready",
                "importing",
                "done",
                "failed",
                "undoing",
                "undone",
                "cancelled",
                name="import_status",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("file_key", sa.String(length=500), nullable=False),
        sa.Column("filename", sa.String(length=500), nullable=False),
        sa.Column("size", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("preview", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("decisions", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
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
            name=op.f("fk_gedcom_imports_created_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tree_id"],
            ["trees.id"],
            name=op.f("fk_gedcom_imports_tree_id_trees"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_gedcom_imports")),
    )
    op.create_index(op.f("ix_gedcom_imports_tree_id"), "gedcom_imports", ["tree_id"], unique=False)
    op.create_table(
        "integrity_issues",
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("media_id", sa.Uuid(), nullable=True),
        sa.Column("tree_id", sa.Uuid(), nullable=True),
        sa.Column("key", sa.String(length=500), nullable=False),
        sa.Column(
            "problem",
            sa.Enum(
                "missing",
                "size_mismatch",
                "hash_mismatch",
                "unreadable",
                name="integrity_problem",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("expected_size", sa.BigInteger(), nullable=True),
        sa.Column("actual_size", sa.BigInteger(), nullable=True),
        sa.Column("expected_sha256", sa.String(length=64), nullable=True),
        sa.Column("actual_sha256", sa.String(length=64), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["media_id"],
            ["media_files.id"],
            name=op.f("fk_integrity_issues_media_id_media_files"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["integrity_runs.id"],
            name=op.f("fk_integrity_issues_run_id_integrity_runs"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tree_id"],
            ["trees.id"],
            name=op.f("fk_integrity_issues_tree_id_trees"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_integrity_issues")),
    )
    op.create_index(
        op.f("ix_integrity_issues_run_id"), "integrity_issues", ["run_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_integrity_issues_run_id"), table_name="integrity_issues")
    op.drop_table("integrity_issues")
    op.drop_index(op.f("ix_gedcom_imports_tree_id"), table_name="gedcom_imports")
    op.drop_table("gedcom_imports")
    op.drop_table("integrity_runs")
