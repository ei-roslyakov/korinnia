# Architecture

## Overview

```
                 ┌──────────────────────────── Docker Compose / Kubernetes ─────────────────────────┐
 browser ──TLS──▶│ ingress / LB ──HTTP──▶ nginx :80                                                 │
                 │                         ├─ /            → built React app (static files)         │
                 │                         ├─ /api/*       → backend (FastAPI :8000)                │
                 │                         └─ /_media/*    → internal: files after backend auth     │
                 │                                                                                  │
                 │   backend (FastAPI) ──┬──▶ PostgreSQL 16 (data + job queue)  ◀── worker          │
                 │                       └──▶ media volume /data/media           ◀── worker         │
                 └──────────────────────────────────────────────────────────────────────────────────┘
```

- **nginx** serves the frontend and proxies `/api`. It mounts the media volume read-only: the
  backend authorises a download and hands it to nginx with `X-Accel-Redirect`, so large files never
  pass through Python.
- **backend** is the REST API (`/api/v1`). On start it runs `alembic upgrade head`.
- **worker** runs the same image with `python -m app.jobs.worker` and consumes jobs from
  PostgreSQL: thumbnails and video previews, GEDCOM imports, weekly integrity checks of stored
  originals.
- **PostgreSQL** holds all structured data *and* the job queue (no Redis).
- **Media volume** (`/data/media`) holds original and derived files as plain files. On Kubernetes
  this is a ReadWriteMany PersistentVolumeClaim shared by backend, worker and nginx.

The reasoning behind these choices is in [decisions.md](decisions.md); tables and conventions are
in [data-schema.md](data-schema.md).

## Tech stack

| Area | Technology |
|---|---|
| Backend | Python 3.15, FastAPI, Pydantic 2 + pydantic-settings, Uvicorn, uv |
| Auth & security | argon2id (argon2-cffi), JWT (PyJWT) in httpOnly cookies, CSRF double-submit cookie, TOTP 2FA (pyotp, segno QR codes, secrets encrypted with `cryptography`) |
| Database | PostgreSQL 16, SQLAlchemy 2 (async, psycopg 3), Alembic migrations |
| File storage | Local filesystem behind a `Storage` abstraction (Docker volume / Kubernetes PVC) |
| Background jobs | procrastinate — PostgreSQL-backed job queue |
| Frontend | React 19, TypeScript, Vite, Tailwind CSS 4, TanStack Query, React Router, react-i18next (en / uk / pl) |
| Tree canvas | React Flow (`@xyflow/react`), elkjs (layered layout in a Web Worker) |
| Content | react-markdown + remark-gfm (raw HTML never rendered) |
| Maps | Leaflet + OpenStreetMap tiles |
| Web server | nginx — static frontend, `/api` reverse proxy, gzip, caching and security headers. Plain HTTP: TLS is terminated by your ingress / load balancer |
| Media processing | Pillow (+ pillow-heif), ffmpeg, poppler `pdftoppm`, `filetype` (content-based type detection) |
| Testing | pytest + pytest-asyncio + httpx (backend); Vitest + Testing Library, Playwright (E2E) |
| Lint / format / types | ruff, mypy (strict); ESLint + typescript-eslint, Prettier; pre-commit |
| CI / delivery | GitHub Actions (lint, types, tests, image builds, E2E against the production stack); Helm chart |

Exact versions are pinned in `backend/uv.lock` and `frontend/package-lock.json`.

## Project structure

```
backend/    FastAPI app (app/{api,core,models,schemas,services,storage,jobs,importers,exporters}),
            Alembic migrations, pytest tests, Dockerfile (dev + prod targets)
frontend/   React + TypeScript app (src/features/* per feature area, src/i18n locales),
            Vitest unit tests, Playwright E2E tests (e2e/)
deploy/     nginx/ (image, config, templates), helm/ (Kubernetes chart), scripts/ (backup, restore)
docs/       Architecture, decisions, data schema, operations
scripts/    Maintenance helpers (performance check, third-party licence notices)
.github/    CI and release workflows
```
