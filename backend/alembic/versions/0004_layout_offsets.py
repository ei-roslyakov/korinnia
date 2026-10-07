"""Manual canvas layout offsets per tree and person.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-07 07:32:36.959245+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "layout_offsets",
        sa.Column("tree_id", sa.Uuid(), nullable=False),
        sa.Column("person_id", sa.Uuid(), nullable=False),
        sa.Column("dx", sa.Float(), nullable=False),
        sa.Column("dy", sa.Float(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["person_id"],
            ["persons.id"],
            name=op.f("fk_layout_offsets_person_id_persons"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tree_id"],
            ["trees.id"],
            name=op.f("fk_layout_offsets_tree_id_trees"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("tree_id", "person_id", name=op.f("pk_layout_offsets")),
    )


def downgrade() -> None:
    op.drop_table("layout_offsets")
