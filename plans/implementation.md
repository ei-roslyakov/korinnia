# Implementation overview

What exists today and how it is built. The reasoning for each choice is in
`docs/decisions.md` (D-numbers below); table details are in `docs/data-schema.md`.

## Stack

- **Backend**: Python 3.12, FastAPI, SQLAlchemy 2 (async, psycopg 3), Alembic, PostgreSQL 16,
  procrastinate (job queue in PostgreSQL), argon2id, JWT in httpOnly cookies, structured JSON logs.
- **Frontend**: React + TypeScript + Vite, TanStack Query, React Flow (canvas), ELK (layout, in a Web
  Worker), Tailwind v4 (themes as CSS variables), react-i18next (en / uk / pl), Leaflet +
  OpenStreetMap, self-hosted Inter and Lora fonts.
- **Runtime**: Docker Compose (postgres, backend, worker, nginx; dev override adds Vite with hot
  reload). nginx serves the built frontend, proxies `/api`, and streams media via
  `X-Accel-Redirect`. Production: Helm chart (`deploy/helm/korinnia`) on Kubernetes via Argo CD.
- **Quality**: pytest (≈290 tests, separate `*_test` database), Vitest (≈130 tests), Playwright E2E
  on a throwaway production-build stack (desktop + mobile), ruff, mypy, eslint, prettier, tsc,
  pre-commit, GitHub Actions CI.

## Repository layout

```
backend/app/
  api/v1/        REST endpoints (trees, persons, events, relationships, places, media, sources,
                 stories, collaboration, insights, history, admin, auth)
  api/deps.py    auth + per-tree role dependencies (TreeViewer … TreeAdmin, Superadmin)
  services/      business logic (trees, users, auth, audit, genealogy/*, demo portraits)
  models/        SQLAlchemy models;  schemas/  Pydantic models
  jobs/          procrastinate app, tasks (media processing, demo family), worker
  storage/       local filesystem storage (atomic writes, SHA-256)
  importers/gedcom/  GEDCOM reader (parser, ANSEL, dates, records → plain data)
  exporters/         placeholder for phase 11
  seed.py, cli.py         demo family seeding; operator CLI (create-superadmin, disable-2fa)
  perf.py                 synthetic large trees for `make perf`
backend/alembic/  migrations (run automatically on backend start)
frontend/src/
  features/      admin, auth, builder, collab, imports, insights, map, media, person, sources,
                 stories, timeline, tree (canvas in tree/canvas)
  components/    shared UI (ui.tsx, Layout, Logo, EmptyState, Skeleton, HeaderSelect, toasts)
  i18n/locales/  en.json, uk.json, pl.json (parity is tested)
  lib/           api client (CSRF), types, dates, kinship terms, hooks, version
frontend/e2e/     Playwright specs
deploy/           nginx image, Helm chart, Argo CD Application, backup/restore scripts
scripts/          third-party-notices.sh (make notices), perf.sh + perf/browser.mjs (make perf)
docs/             decisions, data schema, backup/restore, user guide (stub)
plans/            this folder
```

## What each phase delivered

1. **Scaffolding** — Compose stack, health probes `/healthz` `/readyz`, storage abstraction,
   job queue with heartbeat, security headers/CSP, CI, pre-commit. (D1–D17)
2. **Users and roles** — login with rotating refresh tokens, CSRF double-submit, throttling, TOTP
   2FA with recovery codes, superadmin bootstrap, admin panel (users, invitations by link, audit
   log), per-tree roles viewer < contributor < editor < admin. (D18–D28)
3. **Genealogy API** — people with many names (any script), partial dates, events with
   participants, places with historical names, parent–child links and partnerships, validation
   (errors vs warnings), transliterated search, revisions with restore, soft delete in batches with
   trash. (D29–D40)
4. **Tree canvas** — React Flow + ELK in a worker, focus mode for big trees, search, person side
   panel and full page. (D41–D46)
5. **Builder** — View/Builder toggle, "+" on cards to add relatives atomically, full person editor,
   events, places, family editor, history, delete with preview, drag layout saved as offsets.
   (D47–D53)
6. **Media** — uploads (streamed), content-type detection, originals never modified, worker makes
   web versions/thumbnails/posters, gallery + lightbox, face tags, portrait crop, served only to
   members via nginx. (D54–D59)
7. **Collaboration** — sources and citations on any fact, stories with review workflow,
   contributor suggestions with diff and approval, comments, research questions, data-quality
   panel. (D60–D67)
8. **Insights** — family map, timeline with historical context, relationship calculator (kinship
   terms in uk/en/pl), statistics, "On this day". (D68–D73)
9. **Data safety** — GEDCOM import (preview, duplicate merge, one transaction, undo) and weekly /
   on-demand integrity checks of stored originals; backups are left to the infrastructure.
   (D89–D90)
10. **Hardening and user guide** — read-only share links (D98), performance test `make perf`
   with simplified cards when zoomed out (D97), user guide at `/help` (D99), client IPs only from
   `TRUSTED_PROXIES` via `ProxyHeadersMiddleware` in `app/main.py` (D100), TOTP secrets
   encrypted with Fernet in `core/security.py` (`encrypt_secret` / `decrypt_secret`, D101),
   every page lazy-loaded from `App.tsx` with `Suspense` in the layouts (D102).
- **Tree creation** — any user (`services/users.may_create_trees`: superadmin, or
  `USERS_CAN_CREATE_TREES` and `users.can_create_trees`) creates trees and becomes their admin;
  the superadmin administers the whole site. (D103)

## After phase 8 (polish and operations)

- Tree drawn growing upwards: generation rows, couples side by side, trunk and roots; drag a whole
  branch in any direction, Alt-drag one card; lineage highlight; generation labels. (D74, D76, D83)
- Themes light / dark / archive (sepia) and glass Night (blurred backdrop on `<html>`, frosted `.bg-surface`, solid cards on the canvas); tree styles Simple / Oak / Spring; logo per theme. (D77, D84, D104)
- English by default (`DEFAULT_LANGUAGE`), remembered per user. (D81)
- Demo family for every new user (66 people, 7 generations, several root families, biographies,
  illustrated portraits); `make seed` grows older copies into the current version. (D91)
  (D78, D79)
- Licence "All rights reserved", footer with copyright, app version and third-party notices. (D85)
- Kubernetes: Helm chart, GHCR images, Deploy workflow with automatic patch versions, Argo CD;
  media volume permission fix. (D87)
- Tree management: tree admins rename/delete trees from the tree list, the builder toolbar or tree
  settings; superadmin "Trees" tab lists every tree and restores deleted ones; person delete from
  the builder side panel. (D86)
- Tree export: PNG / PDF download of the whole tree from the canvas (html-to-image, own PDF
  writer in `lib/pdf.ts`). (D88)

## Conventions

- Every change goes through services and is written to the audit log; deletes are soft deletes.
- New UI strings go into all three locale files (a test checks parity); E2E tests use the
  Ukrainian UI (`DEFAULT_LANGUAGE=uk`).
- New decisions get the next D-number in `docs/decisions.md`; README feature statuses are kept
  current; schema changes go into `docs/data-schema.md`.
- Commands: `make up`, `make lint`, `make test`, `make test-e2e`, `make fmt`, `make seed`,
  `make notices`, `make backup` / `make restore`. Dev login: `admin@example.com` /
  `change-me-now-please`.
- Commit and push only when the owner asks; commit messages end with the Co-Authored-By line.
  Pushing to `main` deploys to production.
