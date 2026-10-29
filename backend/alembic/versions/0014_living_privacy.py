"""Privacy of living people: who sees only their basics, and whether portraits show (D114).

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-29 10:00:00+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "trees",
        sa.Column(
            "living_privacy",
            sa.Enum(
                "off",
                "share_links",
                "viewers_and_share_links",
                name="living_privacy",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            server_default="share_links",
            nullable=False,
        ),
    )
    op.add_column(
        "trees",
        sa.Column("show_living_portraits", sa.Boolean(), server_default="false", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("trees", "show_living_portraits")
    op.drop_column("trees", "living_privacy")
