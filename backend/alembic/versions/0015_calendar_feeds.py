"""Calendar feeds: a member's private iCalendar subscription to a tree (D115).

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-29 14:00:00+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "calendar_feeds",
        sa.Column("tree_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "language",
            sa.Enum(
                "uk",
                "en",
                "pl",
                name="feed_language",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("window_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["tree_id"],
            ["trees.id"],
            name=op.f("fk_calendar_feeds_tree_id_trees"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_calendar_feeds_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_calendar_feeds")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_calendar_feeds_token_hash")),
        sa.UniqueConstraint("tree_id", "user_id", name=op.f("uq_calendar_feeds_tree_id_user_id")),
    )
    op.create_index(op.f("ix_calendar_feeds_tree_id"), "calendar_feeds", ["tree_id"])
    op.create_index(op.f("ix_calendar_feeds_user_id"), "calendar_feeds", ["user_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_calendar_feeds_user_id"), table_name="calendar_feeds")
    op.drop_index(op.f("ix_calendar_feeds_tree_id"), table_name="calendar_feeds")
    op.drop_table("calendar_feeds")
