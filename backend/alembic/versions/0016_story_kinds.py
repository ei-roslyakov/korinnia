"""Family recipes and traditions: a kind, a recipe and an occasion on stories (D117).

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-29 18:00:00+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "stories",
        sa.Column(
            "kind",
            sa.Enum(
                "story",
                "recipe",
                "tradition",
                name="story_kind",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            server_default="story",
            nullable=False,
        ),
    )
    op.add_column(
        "stories", sa.Column("recipe", postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )
    op.add_column("stories", sa.Column("occasion", sa.String(length=200), nullable=True))
    op.create_index(op.f("ix_stories_kind"), "stories", ["kind"])


def downgrade() -> None:
    op.drop_index(op.f("ix_stories_kind"), table_name="stories")
    op.drop_column("stories", "occasion")
    op.drop_column("stories", "recipe")
    op.drop_column("stories", "kind")
