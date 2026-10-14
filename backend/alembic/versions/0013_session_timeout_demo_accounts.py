"""Session timeouts and throwaway demo accounts.

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-14 10:00:00+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # NULL for sessions started before this: they get a timeout at their next refresh.
    op.add_column(
        "refresh_tokens",
        sa.Column("session_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("is_sandbox", sa.Boolean(), server_default="false", nullable=False),
    )


def downgrade() -> None:
    # Demo accounts cannot exist without the column: remove them with their trees.
    op.execute("DELETE FROM trees WHERE owner_id IN (SELECT id FROM users WHERE is_sandbox)")
    op.execute("DELETE FROM users WHERE is_sandbox")
    op.drop_column("users", "is_sandbox")
    op.drop_column("refresh_tokens", "session_expires_at")
