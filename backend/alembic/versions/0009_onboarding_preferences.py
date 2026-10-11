"""Onboarding: welcome guide and "What's new" preferences per user.

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-11 07:44:42.619555+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("welcome_dismissed", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column("users", sa.Column("changelog_seen", sa.String(length=32), nullable=True))
    op.add_column(
        "users", sa.Column("show_changelog", sa.Boolean(), server_default="true", nullable=False)
    )
    # People who already use the app do not need the welcome guide (they still get news).
    op.execute("UPDATE users SET welcome_dismissed = true WHERE last_login_at IS NOT NULL")


def downgrade() -> None:
    op.drop_column("users", "show_changelog")
    op.drop_column("users", "changelog_seen")
    op.drop_column("users", "welcome_dismissed")
