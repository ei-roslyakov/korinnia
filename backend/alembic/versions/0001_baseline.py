"""Baseline: extensions + procrastinate job queue schema.

Revision ID: 0001
Revises:
Create Date: 2026-10-07

The procrastinate schema SQL is vendored (alembic/versions/sql/) instead of being read
from the installed library, so this migration is reproducible forever. When upgrading
procrastinate, add a new migration that applies the library's migration files for the
version range (see docs/decisions.md).
"""

from collections.abc import Sequence
from pathlib import Path

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SQL_DIR = Path(__file__).parent / "sql"


def upgrade() -> None:
    # Accent/case-insensitive name search (Cyrillic + Latin) and trigram fuzzy matching.
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    # Executed on the raw DB-API cursor *without* parameters: the SQL contains literal '%'
    # (which psycopg would parse as placeholders) and multiple statements.
    sql = (SQL_DIR / "procrastinate_3.10.0_schema.sql").read_text(encoding="utf-8")
    cursor = op.get_bind().connection.dbapi_connection.cursor()  # type: ignore[union-attr]
    try:
        cursor.execute(sql)
    finally:
        cursor.close()


def downgrade() -> None:
    op.execute(
        """
        DO $$
        DECLARE r record;
        BEGIN
            FOR r IN SELECT p.oid::regprocedure AS sig FROM pg_proc p
                     JOIN pg_namespace n ON n.oid = p.pronamespace
                     WHERE n.nspname = current_schema() AND p.proname LIKE 'procrastinate%'
            LOOP
                EXECUTE 'DROP ROUTINE IF EXISTS ' || r.sig || ' CASCADE';
            END LOOP;
        END $$;
        DROP TABLE IF EXISTS procrastinate_periodic_defers, procrastinate_events,
            procrastinate_jobs, procrastinate_workers CASCADE;
        DROP TYPE IF EXISTS procrastinate_job_status, procrastinate_job_event_type,
            procrastinate_job_to_defer_v1 CASCADE;
        """
    )
