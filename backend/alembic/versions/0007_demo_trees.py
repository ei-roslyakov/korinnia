"""Mark demo trees (each user gets their own copy of the demo family).

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-07 12:00:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "trees", sa.Column("is_demo", sa.Boolean(), server_default="false", nullable=False)
    )
    # Demo trees created by `app.seed` before this flag existed (keep one per owner).
    op.execute(
        """
        UPDATE trees SET is_demo = true WHERE id IN (
            SELECT DISTINCT ON (owner_id) id FROM trees
            WHERE name = 'Родина Коваленків (демо)' AND deleted_at IS NULL
            ORDER BY owner_id, created_at
        )
        """
    )
    op.create_index(
        "uq_trees_demo_owner",
        "trees",
        ["owner_id"],
        unique=True,
        postgresql_where=sa.text("is_demo AND deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_trees_demo_owner", table_name="trees")
    op.drop_column("trees", "is_demo")
