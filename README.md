# Korinnia (Коріння)

**A self-hosted family archive and interactive family tree.**

Korinnia's mission is long-term preservation: to collect *everything* about every family member — names in every spelling, life events, biographies, photos, documents, recordings, stories and sources — in one place, so that future generations can still read it decades from now. Every design decision favours data durability, completeness and open formats, and the archive must stay readable even if this application no longer runs.

> **Status:** Phases 1–8 of 11 are complete (scaffolding; users and roles; core family data; tree canvas; builder; media; sources, stories and collaboration; map, timeline, relationship calculator, statistics and "On this day"). GEDCOM import, integrity checks and scheduled backups are next. See [Features](#features) for what works today.

---

## Tech stack

| Area | Technology |
|---|---|
| Backend | Python 3.12, FastAPI 0.142, Pydantic 2.13 + pydantic-settings, Uvicorn 0.54, uv (package manager) |
| Auth & security | argon2id password hashing (argon2-cffi), JWT (PyJWT) in httpOnly cookies, CSRF double-submit cookie, TOTP 2FA (pyotp, QR codes via segno) |
| Database | PostgreSQL 16, SQLAlchemy 2.1 (async, psycopg 3.3 driver), Alembic 1.20 migrations |
| File storage | Local filesystem behind a `Storage` abstraction, on a Docker volume / Kubernetes PVC at `/data/media` |
| Background jobs | procrastinate 3.10 — PostgreSQL-backed job queue (no Redis) |
| Frontend | React 19, TypeScript 6, Vite 8, Tailwind CSS 4, TanStack Query 5, React Router 8, react-i18next 17 (uk / en / pl) |
| Tree canvas | React Flow 12 (`@xyflow/react`: pan / zoom / minimap, viewport culling), elkjs 0.12 (layered genealogical layout in a Web Worker) |
| Content | react-markdown 10 + remark-gfm (biographies, notes; raw HTML never rendered) |
| Maps | Leaflet 1.9 + OpenStreetMap tiles (place pins; map view planned) |
| Web server | nginx 1.29 — static frontend, `/api` reverse proxy, gzip (incl. pre-compressed assets), caching & security headers. Plain HTTP: TLS is terminated by your ingress / load balancer |
| Media processing | Pillow 12 (+ pillow-heif for iPhone HEIC; thumbnails, web versions, EXIF orientation, portrait crops), ffmpeg 5 (video posters, browser-friendly MP4 / MP3), poppler `pdftoppm` (PDF thumbnails), `filetype` (content-based type detection) |
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
- ✅ UI in English (default, configurable with `DEFAULT_LANGUAGE`), Ukrainian and Polish; each user's choice is remembered
- ✅ Tree logo in the header and on the sign-in page, coloured per theme; self-hosted Lora and Inter fonts (with Cyrillic); illustrated empty states, loading placeholders, toast notifications
- ✅ Tree list with portrait covers, people count and years covered; stories shown magazine-style (cover, reading time, drop cap)
- ✅ Themes: light, dark and archive (sepia), or follow the device setting; remembered per device
- ✅ GitHub Actions CI, pre-commit hooks
- ✅ Basic manual backup / restore scripts (database + media)

### Users & admin
- ✅ Email + password login (argon2id); no public self-registration
- ✅ Sessions: short-lived access + rotating refresh JWTs in httpOnly cookies, refresh-token reuse detection, "sign out everywhere" on password change
- ✅ CSRF protection (double-submit cookie + SameSite)
- ✅ Optional TOTP two-step verification with one-time recovery codes (any user; recommended for admins)
- ✅ Login throttling per email and per IP (PostgreSQL-backed)
- ✅ First superadmin bootstrapped from environment variables; operator CLI for lock-out recovery
- ✅ Multiple trees; per-tree roles: viewer, contributor, editor, admin (enforced on every endpoint, covered by tests)
- ✅ Admin panel: create / deactivate / delete users, superadmin rights, password-reset links, reset 2FA
- ✅ Tree deletion by the tree's admins (soft delete); the admin panel lists every tree, deletes any of them and restores deleted ones
- ✅ Invitations via one-time, expiring links (to a tree with a role, or as superadmin)
- ✅ Tree member management by tree admins (add existing users, invite new ones, change roles, remove)
- ✅ Audit log of every change (who, when, before/after) with filters — global and per tree
- ✅ Profile: display name, interface language (synced across devices), password change
- 📋 Read-only share links (revocable, expiring) — phase 10
- 📋 Sign-up by email (optional, off by default): register, confirm the address by a link, then wait for an admin to grant access to a tree
- 📋 Sign in with Google (OAuth / OpenID Connect), linked to an existing account by verified email; password and 2FA stay available
- ✅ Moderation queue for contributors' suggestions and stories (see below)

### People & relationships (REST API; UI in phases 4–5)
- ✅ People with any number of names (birth, married, nickname, alias, religious…), each in Cyrillic, Latin or other script, with patronymic and maiden name
- ✅ Life events (16 types) with several participants, partial / approximate dates (exact, month, year, about, before, after, between) and places; birth & death exposed as first-class fields
- ✅ Burial details: cemetery, plot, GPS coordinates
- ✅ Places with historical names (e.g. Stanislau → Stanisławów → Stanyslaviv → Ivano-Frankivsk) and coordinates
- ✅ Parent–child links (biological, adoptive, step, foster, unknown) and partnerships (marriage, civil union, partnership) with start/end and end reason
- ✅ Validation: no cycles, no self-relations, max 2 biological parents; warnings for implausible dates (child born before parent, parent younger than 12, death before birth, events outside a lifetime, …)
- ✅ Relatives computed per person: parents, children, partners, full and half siblings
- ✅ Search by any name variant with Ukrainian↔Latin transliteration (KMU 2010), maiden names, or birth/death year
- ✅ Whole-tree graph endpoint for the canvas (2,000 people in ≈80 ms)
- ✅ Full revision history of every change (complete snapshots) and restore of any earlier version
- ✅ Soft delete with impact preview; trash bin with restore (a person comes back together with their relationships and events)
- ✅ Living-person flag inferred when not set (privacy-first default)
- ✅ Demo family for every user: each account gets its own editable copy of a fictional family (25 people, 5 generations), every person with a biography and an illustrated portrait; marked "Demo" in the tree list and deletable (`DEMO_TREE_FOR_NEW_USERS`, `make seed` for existing users)

### Tree view
- ✅ Infinite canvas: drag to pan, wheel / pinch to zoom, fit to screen, zoom buttons, minimap
- ✅ Drawn as a real tree growing upwards: the oldest generation stands on the ground with a trunk and roots, one row per generation above it, partners always side by side, curved brown branches that thin out towards the youngest generations; adoptive/step/foster links dashed; layout (ELK) runs in a Web Worker
- ✅ Person cards: portrait, primary name, life years with uncertainty markers (~1850, <1944) and † for the deceased; coloured accent by gender; hover preview with full name, dates and birthplace
- ✅ Three tree styles to choose from: Simple, Oak (a broad trunk and a leafy crown behind the family) and Spring (leaves at every family knot, blossoms on the youngest branches); remembered per browser
- ✅ Hover or select a person to highlight their line (ancestors, descendants, partners); generation labels beside each row ("III покоління · 1920-ті")
- ✅ Click a card → side panel; full person page with shareable link: all names, birth / death / burial (with map link), facts, rendered Markdown biography, life timeline, relatives with portraits, a life bar with the events of their life, notes for descendants, data notes (editors)
- ✅ Search by any name variant (Cyrillic ↔ Latin), place (incl. historical names) or year; the result is centred and opened
- ✅ Focus mode: 1–6 generations around a person, markers for hidden ancestors/descendants; large trees (>150 people) open in focus mode
- ✅ Works on tablet and mobile (touch pan/zoom, full-width panel)
- ✅ Smooth with 2,000+ people (viewport culling; layout in worker)
- ✅ Gallery, documents, audio/video on the person page; sources, stories, research questions and comments
- ✅ Relationship calculator: "how is B related to A?" with the kinship term in Ukrainian (двоюрідний, троюрідний…; тесть / свекор…), English (first cousin once removed…) or Polish, half / adoptive notes, the closest common ancestors and the path through the tree
- ✅ Family map (OpenStreetMap): places of birth, life, marriage, migration, death and burial (graves at their own GPS point); filters by event type and person, with the person's life path drawn in order
- ✅ Family timeline: every dated event and marriage in chronological order, grouped by decade; filters by event type, person and years; optional historical context (World Wars, Holodomor, Chornobyl, independence…)
- ✅ "On this day": birthdays, wedding anniversaries and memorial days for a date or the coming week / month
- ✅ Statistics: people, generations, period covered, oldest ancestor, longest life, average lifespan, surnames (spellings in different scripts grouped), first names, births and deaths by decade
- ✅ Tree navigation bar with all views; "How are we related?", "On the map" and "Timeline" links on every person page

### Builder mode (editors and admins)
- ✅ View / Builder toggle on the tree
- ✅ "+" buttons on every card: add a parent, child (with the other parent), partner or sibling — created and linked atomically
- ✅ Add an unlinked person; first person of an empty tree
- ✅ Full person editor: all names (any script, type, main name), gender, living, research status, birth / death with partial dates and places, occupation, education, religion, nationality
- ✅ Markdown editor with live preview for biography and notes for descendants; drafts autosaved in the browser and offered for restore
- ✅ Life events editor: type, title, partial date, place, description, participants with roles, burial cemetery / plot / GPS pin
- ✅ Place autocomplete (current and historical names, any script) and "create place" with historical names and a map pin (OpenStreetMap)
- ✅ Family editor: change link types, unlink, link existing people, edit partnership dates and end reason
- ✅ Person history with "restore this version"
- ✅ Delete with impact preview; trash bin page with restore
- ✅ Drag cards anywhere to adjust the layout: a card moves with its whole branch (partners, descendants and their partners); hold Alt to move a single card. Saved per tree as offsets from the automatic layout; reset layout
- ✅ Unsaved-changes warning; server validation errors and date warnings shown in place
- ✅ Sources tab: cite a source for any fact (a name, birth, an event, a parent link, a partnership…)

### Media
- ✅ Drag & drop upload with progress (photos incl. HEIC, document scans, PDFs, audio, video, text documents); large files streamed
- ✅ Originals stored byte-for-byte with SHA-256; type detected from content (HTML/SVG/executables rejected); duplicates detected per tree (link the existing file instead)
- ✅ Background processing: EXIF-rotated web versions and thumbnails, video posters + MP4, MP3 for non-browser audio, PDF first-page thumbnails; status, failure reasons, retry
- ✅ Person gallery with lightbox (keyboard navigation, captions, date, place, people), documents list, audio and video players
- ✅ Face / person tagging in group photos (draw a rectangle); names shown on the photo and linked
- ✅ Portrait: choose a photo and crop a square (derived image, original untouched); shown on tree cards and person pages
- ✅ Gallery order per person; title, description, partial date, place per item; history and trash
- ✅ Files served only to tree members (API checks access, nginx streams via `X-Accel-Redirect`, range requests for video)

### Sources, stories & collaboration
- ✅ Source library per tree (civil and church records, archive documents, census, newspapers, letters, oral history, books…) with archive, reference number and URL; search in any script
- ✅ Citations on any fact: a person or one of their fields, a name, an event, a parent link, a partnership or a media item; page / sheet and quality (primary, secondary, family tradition, unverified); "sources" section on the person page grouped by source
- ✅ Stories and memories in Markdown with narrator, partial date and several people; lifecycle draft → on review → published (contributors submit, editors publish or return with a comment)
- ✅ Edit suggestions from contributors (person fields and events) with a before / after diff; editors approve (applied and audited as the reviewer) or reject with a comment
- ✅ Moderation page with a pending badge on the tree toolbar
- ✅ Comments on people and stories; open research questions per person (open → resolved with an answer)
- ✅ Data-quality panel: people without a birth record, without a photo, without any source, with date problems, and open research questions
- ✅ Sources, citations and stories have full history and go through the trash bin
- ✅ Media picker (tree library, search, upload for editors) to attach scans to sources and photos / documents to stories; comments on photos and videos in the lightbox

### Data safety
- 📋 GEDCOM 5.5.1 import with preview and duplicate detection
- 📋 AI-assisted import from social media: upload an exported archive (e.g. Facebook / Instagram data download) or posts and photos; AI suggests people, relationships, dates, places and stories for an editor to review before anything is saved
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

Sign in as the dev superadmin: **`admin@example.com` / `change-me-now-please`** (from `SUPERADMIN_EMAIL` / `SUPERADMIN_PASSWORD` in `.env`; created on first start only). Every new account automatically gets its own copy of the demo family (25 people, 5 generations, with biographies and illustrated portraits); `make seed` gives one to existing users and fills in anything missing in older copies.

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
| `SUPERADMIN_EMAIL` / `SUPERADMIN_PASSWORD` | First administrator, created on first start if no superadmin exists (min. 10 characters). Changing them later has no effect |
| `PUBLIC_BASE_URL` | Public URL of the app, used to build invitation and password-reset links |
| `COOKIE_SECURE` | `true` (default) marks auth cookies HTTPS-only. Set `false` only for plain-HTTP local development |
| `MAX_UPLOAD_SIZE_MB` | Maximum size of one upload; also sets nginx `client_max_body_size` |
| `DEFAULT_LANGUAGE` | Interface language for visitors who have not chosen one and for new accounts: `en` (default), `uk` or `pl` |
| `DEMO_TREE_FOR_NEW_USERS` | Give each new account its own copy of the demo family (default `true`; set `false` for a production archive) |
| `WORKER_CONCURRENCY` | Number of jobs the worker runs in parallel |
| `HTTP_PORT` | Host port for nginx (8080 in dev) |

### Everyday commands

```bash
make help            # list all commands
make logs s=backend  # follow logs of one service
make test            # backend (pytest, separate korinnia_test DB) + frontend (Vitest)
make test-e2e        # Playwright on a throwaway production-build stack (your data is untouched)
make lint            # ruff, mypy, eslint, prettier, tsc
make fmt             # auto-format everything
make migrate         # apply migrations manually
make revision m="add person table"   # autogenerate a migration
make seed            # demo family for every user who has none (safe to re-run)
make psql            # database shell
make down            # stop (volumes, i.e. your data, are kept)
```

The pre-commit hooks are optional but recommended: `cd backend && uv run pre-commit install`.

### Operator commands (lock-out recovery)

There's no email sending: administrators copy invitation and password-reset links from the UI and pass them on. If the only administrator is locked out, use the CLI inside the backend container:

```bash
docker compose exec backend python -m app.cli reset-link admin@example.com     # one-time reset link
docker compose exec backend python -m app.cli disable-2fa admin@example.com    # lost authenticator
docker compose exec backend python -m app.cli create-superadmin you@example.com "Your Name"
```

### Production

`make up-prod` (or `docker compose -f docker-compose.yml up -d --build`) runs the stack without dev overrides: the frontend is built into the nginx image and the API docs are off. Before using it in production, set `ENVIRONMENT=production`, a strong `SECRET_KEY` and `POSTGRES_PASSWORD`, `PUBLIC_BASE_URL`, `COOKIE_SECURE=true`, a superadmin password, and `HTTP_PORT`. Put nginx behind your TLS-terminating ingress or load balancer, which should forward `X-Forwarded-Proto` and send HSTS.

### Troubleshooting

- **Port already in use:** change `HTTP_PORT` in `.env`, or stop whatever is using 5432, 8000 or 5173.
- **`make up` waits forever / a service is unhealthy:** check `make ps` and `make logs s=backend`. The backend only becomes healthy after migrations succeed.
- **Frontend dependencies changed:** `docker compose restart frontend`, which runs `npm ci` on start.
- **Start from scratch (deletes all data):** `docker compose down -v`.
- **"Too many failed attempts":** sign-in is throttled for 15 minutes after 5 failed attempts per email (20 per IP).
- **Login works but you're logged out immediately:** with plain HTTP, `COOKIE_SECURE` must be `false`.
- **Apple Silicon / Linux permission issues on the media volume:** containers run as uid 1000. Named volumes inherit the right ownership automatically, but a bind mount must be writable by uid 1000.

## Project structure

```
backend/    FastAPI app (app/{api,core,models,schemas,services,storage,jobs,importers,exporters}),
            Alembic migrations, pytest tests, Dockerfile (dev + prod targets)
frontend/   React + TypeScript app (src/features/* per feature area, src/i18n locales),
            Vitest unit tests, Playwright E2E tests (e2e/)
deploy/     nginx/ (image, config, templates), scripts/ (backup.sh, restore.sh)
docs/       Architecture decisions, data schema, backup & restore, user guide
scripts/    Maintenance helpers (third-party licence notices)
.github/    CI workflow
```

## Backup & restore

`make backup` writes `backups/<UTC timestamp>/` containing a `pg_dump` of the database, a plain `tar` of the media volume and a `SHA256SUMS` file. `make restore dir=backups/<timestamp>` verifies the checksums, then replaces the database and the media. Scheduled backups, retention and off-site copies come in phase 9. See [docs/backup-restore.md](docs/backup-restore.md).

## License

Copyright © 2026 Yevhenii Rosliakov. **All rights reserved.** Korinnia is proprietary software: no licence to use, copy, modify or distribute it is granted without written permission (see [LICENSE](LICENSE)). Family content added to an installation belongs to its authors.

Korinnia uses open-source components under their own licences; their notices are in [frontend/public/third-party-notices.txt](frontend/public/third-party-notices.txt), served by the app at `/third-party-notices.txt` and linked in the footer. Regenerate it after changing dependencies with `make notices`. The footer also shows the running release (set by the Deploy workflow; "dev" locally).

## Documentation

- [docs/decisions.md](docs/decisions.md): architecture decision log
- [docs/data-schema.md](docs/data-schema.md): data schema and conventions
- [docs/backup-restore.md](docs/backup-restore.md): backup and restore procedure
- [docs/user-guide.md](docs/user-guide.md): user guide
