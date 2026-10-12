# Roadmap

_Last updated: 2026-10-12 (phase 10 done; next: "You are in a family tree")_

Korinnia (Коріння) is a self-hosted family archive and interactive family tree. It is delivered in
11 phases; after each phase the work stops for review before the next one starts.

## Status at a glance

| Phase | Scope | Status |
|---|---|---|
| 1 | Scaffolding: Docker Compose, FastAPI, PostgreSQL, worker, nginx, storage, health, CI | ✅ done |
| 2 | Authentication, users, per-tree roles, admin panel, audit log | ✅ done |
| 3 | Core genealogy API: people, names, events, places, relationships, history, trash | ✅ done |
| 4 | Tree canvas, person page, search | ✅ done |
| 5 | Builder mode (editing UI) | ✅ done |
| 6 | Media: photos, documents, audio, video, face tags, portraits | ✅ done |
| 7 | Sources, citations, stories, suggestions, moderation, comments, data quality | ✅ done |
| 8 | Map, timeline, relationship calculator, statistics, "On this day" | ✅ done |
| — | Post-phase-8 polish: tree drawn growing upwards, themes, tree styles, demo family, licence, deploy to Kubernetes, tree rename/delete, tree export to PNG / PDF | ✅ done |
| — | After phase 9: bigger demo family (66 people, D91), cards never overlap (D92), couple links (D93), share a tree by email (D94), welcome guide + What's new (D95), GEDCOM export (D96) | ✅ done |
| — | After phase 10: every user creates their own trees (D103) | ✅ done |
| 9 | GEDCOM import, integrity checks of stored files (backups: infrastructure) | ✅ done |
| 10 | Hardening and user guide | ✅ done (awaiting deploy) |
| 11 | Exports (family archive) | 📋 planned |

## Live deployment

- Production: https://korinnia.app (also korinnia.rosliakov.club), Kubernetes cluster `infra-k8s-001`,
  namespace `infra-k8s-001-korinnia`, deployed by Argo CD from
  `deploy/argocd/infra-k8s-001/korinnia.yaml`.
- Every push to `main` (except `*.md` and `deploy/argocd/**`) runs the **Deploy** workflow: builds
  and pushes images to GHCR, publishes the Helm chart, bumps the patch version (v0.0.N), tags it, and
  commits the new version into the Argo CD Application ("Deploy vX [skip ci]").
- Last deployed at the time of writing: v0.0.16 (GEDCOM export, performance work, share links;
  migration 0010 applied 2026-10-11). The user guide goes out with the next deploy.
- Production demo copies are updated with `python -m app.seed --all-users` in the backend pod
  after a deploy that changes the demo family.
- Media volume: NFS (`nfs-csi`), fixed by an init container (D87).

## Phase 9 (done 2026-10-08)

- GEDCOM 5.5 / 5.5.1 import with preview, duplicate candidates (merge instead of creating),
  one-transaction import with per-item warnings, undo via the trash (D89).
- Integrity checks of stored originals: weekly + "Check now" on the admin System page (D90).
- **Backups are not part of the app**: the owner handles scheduled backups, retention and
  off-site copies on the infrastructure side (D90). `make backup` / `make restore` stay for
  manual use.
- Possible follow-ups (not planned yet): import photos referenced by a GEDCOM (GEDZIP / a zip of
  the media folder); fill missing facts of a merged person from the file; email the admin when
  an integrity check finds problems.

## Phase 10 — hardening and user guide (done 2026-10-12)

- ✅ Read-only share links (revocable, expiring) — D98. Possible follow-up: hide living people
  from link visitors.
- ✅ Performance test with large trees: `make perf` (PEOPLE=2000 by default), results in
  `docs/performance.md`; simplified cards when zoomed out, faster GEDCOM export — D97.
- ✅ Full user guide in Ukrainian and English, in the app at `/help` — D99. Possible follow-up:
  a Polish translation.
- ✅ Route-level code splitting: first load 1.3 MB → 450 kB (gzip 400 → 143 kB) — D102.
- ✅ Trusted proxies: `X-Forwarded-For` believed only from `TRUSTED_PROXIES` (default private
  networks) — D100.
- ✅ TOTP secrets encrypted at rest (migration 0011, optional `DATA_ENCRYPTION_KEY`) — D101.
- (Already done early: couple-aware layout, D74.)

## Now: "You are in a family tree" (agreed 2026-10-12)

The owner's request: a user should learn that they appear as a person in some tree, with a
permanent notice on the main page. Agreed design (no automatic name matching — it guesses wrong
and reveals other families' trees):

1. A tree editor links a person to a user account ("This person is andrii@example.com").
2. That user sees a permanent notice on the tree list: "You appear in *Kovalenko family* as
   Andrii Kovalenko, added by Halyna".
3. Not a member yet → **Request access**; the tree's admins approve (choosing a role) or decline;
   nothing of the tree is visible before that. Already a member → "This is you" with a link to
   the card.
4. Bonus: a "You" marker on the linked card; the tree can open centred on you; "How am I
   related to…" from your own card.

## Phase 11: exports (planned)

- Family archive ZIP: offline static website, JSON + GEDCOM, Markdown, original media with manifest,
  README (uk / en)
- Printable PDF family book
- (Done early: GEDCOM export with an option to hide living people, D96.)
- (Already done early: PNG / PDF download of the tree view, D88.)

## Backlog (agreed ideas, not scheduled)

- Sign-up by email (optional, off by default): register, confirm by link, wait for an admin to grant
  access
- Sign in with Google (OAuth / OpenID Connect), linked to an existing account by verified email
- AI-assisted import from social media exports (Facebook / Instagram data download): AI suggests
  people, relationships, dates, places and stories for an editor to review before saving
- Optional, after all phases: letters to descendants (sealed until a date), duplicate detection and
  merge, PWA

## Open issues and things to keep in mind

- **Vite dev cache breaks after running tests locally.** `make lint` / `make test` run `npm ci` in a
  container that shares `node_modules` with the dev server, which wipes Vite's pre-bundled deps; the
  tree canvas then shows empty (504 "Outdated Optimize Dep" for `elkjs`). Workaround:
  `docker compose restart frontend`. Proposed fix (not applied, needs the owner's OK): move Vite's
  `cacheDir` out of `node_modules` in dev.
- **Security-scan changes were reverted** (commit 93c568f) because the app stopped loading; the
  suspected cause is the dev nginx/Vite HMR path change. Do not re-apply the uv `exclude-newer`
  cooldown, the nginx `/__vite_hmr` path or the E2E RegExp edits without asking.
- The person side panel in View mode has no delete (only in Builder mode, by design).
- The dev database holds synthetic trees from the performance work ("Великий родовід (тест,
  2000/5000)", "Імпорт 2000 (тест)"); delete them from the tree list when no longer needed.
- Running `make test-e2e` while the dev stack is up restarted the dev backend/worker/frontend
  once (2026-10-08) and left dev nginx with stale upstream addresses (502); fix:
  `docker compose restart nginx`. Cause not investigated.
