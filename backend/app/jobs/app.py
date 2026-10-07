"""Procrastinate app: a PostgreSQL-backed job queue (no Redis).

Run the worker with:  python -m app.jobs.worker
Its schema is managed by Alembic (see alembic/versions/0001_baseline.py).
"""

from __future__ import annotations

import procrastinate

from app.core.config import get_settings

app = procrastinate.App(
    connector=procrastinate.PsycopgConnector(conninfo=get_settings().libpq_conninfo),
    import_paths=["app.jobs.tasks"],
)
