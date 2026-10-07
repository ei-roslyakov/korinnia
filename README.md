# Korinnia (Коріння)

**A self-hosted family archive and interactive family tree.**

Korinnia's mission is long-term preservation: to collect *everything* about every family member — names in every spelling, life events, biographies, photos, documents, recordings, stories and sources — in one place, so that future generations can still read it decades from now. Every design decision favours data durability, completeness and open formats, and the archive must stay readable even if this application no longer runs.

> **Status:** Phase 1 of 11 (scaffolding) is complete. See [Features](#features) for what works today.

---

## Tech stack

| Area | Technology |
|---|---|
| Backend | Python 3.12, FastAPI 0.142, Pydantic 2.13 + pydantic-settings, Uvicorn 0.54, uv (package manager) |
| Database | PostgreSQL 16, SQLAlchemy 2.1 (async, psycopg 3.3 driver), Alembic 1.20 migrations |
| File storage | Local filesystem behind a `Storage` abstraction, on a Docker volume / Kubernetes PVC at `/data/media` |
| Background jobs | procrastinate 3.10 — PostgreSQL-backed job queue (no Redis) |
| Frontend | React 19, TypeScript 6, Vite 8, Tailwind CSS 4, TanStack Query 5, React Router 8, react-i18next 17 (uk / en / pl) |
| Frontend (planned) | React Flow (canvas), elkjs (genealogical layout), Leaflet + OpenStreetMap (maps) |
| Web server | nginx 1.29 — static frontend, `/api` reverse proxy, gzip (incl. pre-compressed assets), caching & security headers. Plain HTTP: TLS is terminated by your ingress / load balancer |
| Media processing (planned) | Pillow (thumbnails, EXIF orientation), ffmpeg (audio/video previews), PDF thumbnails |
| Book / PDF (planned) | WeasyPrint |
| Testing | pytest 9 + pytest-asyncio + pytest-cov + httpx (backend); Vitest 5 + Testing Library + Playwright 1.63 (frontend / E2E) |
| Lint / format / types | ruff 0.16, mypy 2.4 (strict); ESLint 10 + typescript-eslint, Prettier 3.9; pre-commit |
| CI | GitHub Actions: lint, type checks, tests, Docker image builds, E2E against the production stack |
| Runtime | Docker Compose (Node 22 and Python 3.12 run inside containers) |

## Features

Legend: ✅ implemented · 🚧 in progress · 📋 planned

### Platform & infrastructure
- ✅ Docker Compose stack: PostgreSQL, backend (API), worker (jobs), nginx; dev override with hot reload
- ✅ Alembic migrations applied automatically on backend start
- ✅ File storage abstraction (local volume / PVC): atomic writes, SHA-256 on every write, originals never overwritten, path-traversal protection
- ✅ PostgreSQL job queue with worker (queues: `default`, `media`, `maintenance`) and a periodic heartbeat
- ✅ Health probes `/healthz` (liveness) and `/readyz` (database + storage)
- ✅ Structured JSON logging (backend, worker, nginx access log)
- ✅ Security headers (CSP, nosniff, frame-deny, referrer & permissions policy)
- ✅ UI shell with Ukrainian (default), English and Polish
- ✅ GitHub Actions CI, pre-commit hooks
- ✅ Basic manual backup / restore scripts (database + media)

### Users & admin
- 📋 Email + password login, JWT in httpOnly cookies, CSRF protection, optional TOTP 2FA for admins
- 📋 Superadmin bootstrapped from environment variables
- 📋 Per-tree roles: viewer, contributor, editor, admin
- 📋 Admin panel: users, invitations, password resets, role assignment
- 📋 Login rate limiting; read-only share links (revocable, expiring)

### People & relationships
- 📋 People with multiple names (birth, married, nickname, religious…; Cyrillic + Latin)
- 📋 Life events with partial / approximate dates and places; birth & death as first-class fields
- 📋 Parent–child (biological, adoptive, step, foster) and partnerships; validation (cycles, implausible dates)
- 📋 Places with historical names and coordinates; burial details
- 📋 Revision history for every change, restore of previous versions, soft delete with trash bin

### Tree view
- 📋 Infinite canvas (pan, zoom, fit, minimap) with person cards
- 📋 Person page: names, timeline, biography (Markdown), gallery, documents, stories, sources, relatives
- 📋 Search by any name variant, place or year; focus mode (N generations)
- 📋 Relationship calculator, map view, family timeline, "On this day", statistics

### Builder mode
- 📋 Add parents / children / partners / siblings from a person card
- 📋 Full person editor with Markdown biography and autosaved drafts
- 📋 Events editor with place autocomplete and map pin
- 📋 Persisted manual node positions; data-quality panel

### Media
- 📋 Drag & drop upload (photos, scans, PDFs, audio, video); originals kept untouched
- 📋 Thumbnails and web versions in the background; avatar crop as a derived image
- 📋 Face / person tagging in group photos; lightbox; audio / video players

### Sources, stories & collaboration
- 📋 Sources and citations on any fact
- 📋 Stories linked to several people (draft → review → published)
- 📋 Edit suggestions from contributors with a moderation queue; comments; open research questions

### Data safety
- 📋 GEDCOM 5.5.1 import with preview and duplicate detection
- 📋 Periodic integrity check of stored originals (SHA-256)
- 📋 Scheduled backups with retention and an off-site copy (3-2-1)

### Export (final phase)
- 📋 Family archive ZIP: offline static website, JSON + GEDCOM, Markdown, original media with manifest, README (uk / en)
- 📋 Printable PDF family book
- 📋 GEDCOM export; PNG / PDF export of the tree view; option to hide living persons

### Optional (after all phases)
- 📋 Letters to descendants (sealed until a date); duplicate detection & merge; PWA

## Architecture

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

- **nginx** serves the frontend and proxies `/api`. It mounts the media volume read-only so that, from phase 6, the backend can authorise a download and hand it to nginx with `X-Accel-Redirect` (no large files pass through Python).
- **backend** is the REST API (`/api/v1`). On start it runs `alembic upgrade head`.
- **worker** runs the same image with `python -m app.jobs.worker` and consumes jobs from PostgreSQL. Later phases add thumbnails, video previews, integrity checks, backups and exports.
- **PostgreSQL** holds all structured data *and* the job queue.
- **Media volume** (`media`, mounted at `/data/media`) holds original and derived files as plain files. On Kubernetes this is a PersistentVolumeClaim shared by backend, worker and nginx.

## Development setup

**Prerequisites:** Docker with Docker Compose v2, and `make`. Node and Python are *not* needed on the host because everything runs in containers. Optionally, install [uv](https://docs.astral.sh/uv/) to run backend tools directly.

1. **Clone:** `git clone <repo-url> korinnia && cd korinnia`
2. **Configure:** `cp .env.example .env`. `make up` does this automatically if `.env` is missing.
3. **Start:** `make up`. This builds the images and starts PostgreSQL, the backend (which applies migrations), the worker, the Vite dev server and nginx, then waits until they're healthy.
4. **Open:** <http://localhost:8080>

Seed data (`make seed`) arrives with the data model in phase 3. A dev superadmin, configured through `SUPERADMIN_EMAIL` / `SUPERADMIN_PASSWORD` in `.env`, arrives in phase 2.

### URLs (development)

| What | URL |
|---|---|
| App (through nginx, hot reload) | http://localhost:8080 |
| API docs (Swagger UI) | http://localhost:8080/api/docs |
| Backend directly | http://localhost:8000 |
| Vite dev server directly | http://localhost:5173 |
| PostgreSQL | `localhost:5432` (user / password from `.env`) |

### Key environment variables (`.env`)

| Variable | Purpose |
|---|---|
| `ENVIRONMENT` | `development` or `production`. Production disables the API docs |
| `SECRET_KEY` | Signs auth tokens. Generate with `openssl rand -hex 32` |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | Database credentials |
| `SUPERADMIN_EMAIL` / `SUPERADMIN_PASSWORD` | First administrator, created on first start (phase 2) |
| `MAX_UPLOAD_SIZE_MB` | Maximum size of one upload; also sets nginx `client_max_body_size` |
| `WORKER_CONCURRENCY` | Number of jobs the worker runs in parallel |
| `HTTP_PORT` | Host port for nginx (8080 in dev) |

### Everyday commands

```bash
make help            # list all commands
make logs s=backend  # follow logs of one service
make test            # backend (pytest, separate korinnia_test DB) + frontend (Vitest)
make test-e2e        # Playwright against the running stack
make lint            # ruff, mypy, eslint, prettier, tsc
make fmt             # auto-format everything
make migrate         # apply migrations manually
make revision m="add person table"   # autogenerate a migration
make psql            # database shell
make down            # stop (volumes, i.e. your data, are kept)
```

The pre-commit hooks are optional but recommended: `cd backend && uv run pre-commit install`.

### Production

`make up-prod` (or `docker compose -f docker-compose.yml up -d --build`) runs the stack without dev overrides: the frontend is built into the nginx image and the API docs are off. Before using it in production, set `ENVIRONMENT=production`, a strong `SECRET_KEY` and `POSTGRES_PASSWORD`, and `HTTP_PORT`. Put nginx behind your TLS-terminating ingress or load balancer, which should forward `X-Forwarded-Proto` and send HSTS.

### Troubleshooting

- **Port already in use:** change `HTTP_PORT` in `.env`, or stop whatever is using 5432, 8000 or 5173.
- **`make up` waits forever / a service is unhealthy:** check `make ps` and `make logs s=backend`. The backend only becomes healthy after migrations succeed.
- **Frontend dependencies changed:** `docker compose restart frontend`, which runs `npm ci` on start.
- **Start from scratch (deletes all data):** `docker compose down -v`.
- **Apple Silicon / Linux permission issues on the media volume:** containers run as uid 1000. Named volumes inherit the right ownership automatically, but a bind mount must be writable by uid 1000.

## Project structure

```
backend/    FastAPI app (app/{api,core,models,schemas,services,storage,jobs,importers,exporters}),
            Alembic migrations, pytest tests, Dockerfile (dev + prod targets)
frontend/   React + TypeScript app (src/features/* per feature area, src/i18n locales),
            Vitest unit tests, Playwright E2E tests (e2e/)
deploy/     nginx/ (image, config, templates), scripts/ (backup.sh, restore.sh)
docs/       Architecture decisions, data schema, backup & restore, user guide
.github/    CI workflow
```

## Backup & restore

`make backup` writes `backups/<UTC timestamp>/` containing a `pg_dump` of the database, a plain `tar` of the media volume and a `SHA256SUMS` file. `make restore dir=backups/<timestamp>` verifies the checksums, then replaces the database and the media. Scheduled backups, retention and off-site copies come in phase 9. See [docs/backup-restore.md](docs/backup-restore.md).

## Documentation

- [docs/decisions.md](docs/decisions.md): architecture decision log
- [docs/data-schema.md](docs/data-schema.md): data schema and conventions
- [docs/backup-restore.md](docs/backup-restore.md): backup and restore procedure
- [docs/user-guide.md](docs/user-guide.md): user guide
