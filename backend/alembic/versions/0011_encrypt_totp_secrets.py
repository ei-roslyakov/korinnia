"""Encrypt two-step verification secrets at rest.

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-12 09:00:00+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.security import ENCRYPTED_PREFIX, decrypt_secret, encrypt_secret

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _rewrite(convert: object, *, encrypted: bool) -> None:
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, totp_secret FROM users WHERE totp_secret IS NOT NULL"))
    for user_id, secret in rows.all():
        if secret.startswith(ENCRYPTED_PREFIX) == encrypted:
            conn.execute(
                sa.text("UPDATE users SET totp_secret = :s WHERE id = :id"),
                {"s": convert(secret), "id": user_id},  # type: ignore[operator]
            )


def upgrade() -> None:
    op.alter_column("users", "totp_secret", type_=sa.String(length=255))
    _rewrite(encrypt_secret, encrypted=False)


def downgrade() -> None:
    _rewrite(decrypt_secret, encrypted=True)
    op.alter_column("users", "totp_secret", type_=sa.String(length=64))
