# Work log

Newest first. One entry per finished task: what changed, why, commit, anything left open.

## 2026-10-14

- **Session timeout + public demo login (D105, D106)** — owner's request: a shared demo login
  (`demo@example.com` / `demo@example.com`) where every visitor gets a fresh state, a 30-minute
  demo session, and a session-expired popup with a way to refresh the session for everyone.
  - Sessions: `refresh_tokens.session_expires_at` (migration 0013), `SESSION_TIMEOUT_MINUTES`
    (8 h); access tokens capped (`sx` claim); `POST /auth/session/extend`; frontend
    `SessionWatch` (warning 2 min before with "Stay signed in", then a popup asking for the
    password, page stays open; `RequireAuth` doesn't redirect meanwhile).
  - Demo: `services/demo_sessions.py` — each demo sign-in creates a hidden `is_sandbox` account
    with its own demo family; no extension; worker job `demo.purge_ended` every 5 min deletes
    ended ones (trees, files, audit). Limits per IP / active count; no sharing, 2FA, password,
    uploads > 20 MB; hidden from admin. "Try the demo" + credentials on the sign-in page (from
    `/meta`), countdown badge in the header, "Start a new demo" when it ends.
  - Speed: portraits cached per process and warmed at start-up; one `demo.portraits` job per new
    demo copy instead of 132 (also for normal new users) — found because demo jobs delayed the
    E2E photo upload. Demo sign-in ~0.9 s in dev.
  - Fixed on the way: docker-compose did not pass `DATA_ENCRYPTION_KEY`, `TRUSTED_PROXIES`,
    `USERS_CAN_CREATE_TREES` from `.env` (defaults applied); an empty `DATA_ENCRYPTION_KEY` now
    counts as unset.
  - Production: `DEMO_LOGIN_ENABLED: "true"` in the Argo CD values (goes live with the push).
  - Tests: backend 330, frontend 165, E2E 27 (×2 green); `e2e/demo.spec.ts`.
  - Open: existing sessions in production get their 8-hour end at their next refresh.

## 2026-10-12

- **Night (glass) theme (D104)** — owner asked for more themes with a blurred background;
  Meadow and Sky were built too, but only Night was kept. CSS only (`index.css`): blurred radial-gradient backdrop on a fixed layer, frosted
  `.bg-surface` panels, solid cards inside `.react-flow`; exports use `--k-surface-solid` /
  `--k-canvas-solid`; `isDarkTheme()` for canvas colour mode and map tiles. Checked with
  screenshots of the tree list and canvas. Guide (uk/en), changelog
  `2026-10-12.3`.
- **Every user creates their own trees (D103)** — owner's request: "user should create his own
  tree, he is an admin in his space; superadmin is admin across admins". `POST /trees` open to
  any user allowed by `may_create_trees` (superadmin, or `USERS_CAN_CREATE_TREES` and
  `users.can_create_trees`, migration 0012); creator becomes owner + admin; `owner_id` for
  someone else stays superadmin-only. `/auth/me` returns `can_create_trees`; tree list shows
  "New tree" / "Import GEDCOM" by it; Admin → Users "Stop / Allow creating trees". Guide (uk/en),
  welcome text, changelog `2026-10-12.2`. Tests: backend +2 (permissions matrix updated),
  frontend +1.
- **Phase 10 finished: code splitting, trusted proxies, TOTP encryption (D100–D102)**
  - Trusted proxies: uvicorn believed `X-Forwarded-For` from anyone and took the leftmost
    (client-written) entry, so the per-IP login limit could be dodged. Now
    `ProxyHeadersMiddleware` in `app/main.py` with `TRUSTED_PROXIES` (default loopback + private
    networks); uvicorn runs with `--no-proxy-headers`. Checked production first: real public IPs
    reach the audit log through ingress → nginx (pod IPs 10.244.x), which the default covers.
  - TOTP secrets: `enc1:` + Fernet, key from `DATA_ENCRYPTION_KEY` or derived from
    `SECRET_KEY` (HKDF); migration 0011 encrypts existing secrets (round-tripped up/down on dev
    data). New dependency `cryptography` (uv.lock, notices regenerated).
  - Code splitting: every page except sign-in / tree list / not found is `React.lazy`; main
    script 1,312 → 450 kB (gzip 400 → 143 kB). `vite:preloadError` reloads once after a deploy.
    Fixed a share-link race it exposed (stale session check overwrote the new session).
  - Changelog `2026-10-12`. Tests: backend 322, frontend 159, E2E 25 (×3 repeat green). (6b05c38)
  - Production after deploy: migration 0011 runs on start; nothing to configure. Before ever
    rotating `SECRET_KEY`, set `DATA_ENCRYPTION_KEY` (else 2FA codes stop working).
- **Roadmap**: agreed design for "You are in a family tree" (next task).

## 2026-10-11

- **Phase 10: user guide (D99)** — `/help` page (public) rendering
  `frontend/src/features/help/guide.uk.md` / `guide.en.md` (12 sections: sign-in, trees,
  exploring, builder, media, sources, stories, discovery, roles & sharing, import/export,
  administration, tips) with a table of contents; footer "User guide", link in the welcome
  guide; Polish → English with a note. `docs/user-guide.md` points to the files; CLAUDE.md asks
  to update both guides with user-visible changes. Tests: frontend 159. (commit "User guide in the app")
- **Phase 10: share links (D98)** — `share_links` table (migration 0010), service
  `services/share_links.py`, API `/trees/{id}/share-links` (admins) + `/share/{token}/open`,
  `/share/session`, `/share/leave`; `tree_access` accepts the `korinnia_share` cookie for GET
  (guest user, viewer role; also for signed-in non-members). Frontend: `/s/:token` page,
  `RequireAuth` lets link visitors into that tree, header "Shared view" + "Sign in", link
  management in the Share dialog; GEDCOM button hidden for visitors. Tests: backend 3 new,
  frontend 4 new, E2E `share.spec.ts`. (commit "GEDCOM export, performance test, share links")
- **Phase 10: performance test (D97)** — `python -m app.perf` (synthetic tree generator),
  `make perf` (throwaway prod stack, API + Playwright timings), `make perf-tree`;
  `docs/performance.md`. Fixes: simplified cards below 45 % zoom + lazy hover preview (whole
  2,000-person tree 2.4 → 1.5 s, longest task 764 → 284 ms); GEDCOM export no longer quadratic
  (5,000 people 6.3 → 0.43 s). (commit "GEDCOM export, performance test, share links")
- **GEDCOM export (D96)** — `app/exporters/gedcom.py` + `GET /trees/{id}/export/gedcom`
  (`living=false` hides living people's details; audited `tree.export`); "GEDCOM" in the canvas
  Download box with a small dialog. Importer now reads an event's TYPE as its title for all
  events. Round-trip test: demo family → GEDCOM → import into an empty tree = same people,
  links, couples. Changelog entry `2026-10-11.2` (same-day ids get ".2"; the news dialog
  dates entries by their first 10 characters — fixed a crash this would have caused).
  Tests: backend 314, frontend 152, E2E 23. (commit "GEDCOM export, performance test, share links")
- **Welcome guide + "What's new" (D95)** — popups at sign-in with "don't show again" /
  "don't show news" checkboxes; footer links "Getting started" / "What's new". Migration 0009
  (`users.welcome_dismissed`, `changelog_seen`, `show_changelog`; existing users skip the
  guide). Changelog in `frontend/src/features/onboarding/changelog.ts` — CLAUDE.md now asks to
  add an entry for every user-visible change. E2E closes the popups via `e2e/popups.ts`.
  Tests: backend 309, frontend 151, E2E 23. (commit "Welcome guide and What's new")
- **Share a tree by email (D94)** — "Share" next to Rename/Delete (tree cards and builder
  toolbar, tree admins): email + access level, list of who has access, link to Members.
  `POST /trees/{id}/members` got `invite` (default true); `invite: false` → 404
  `no_user_with_email` ("No user with this email exists") and no invitation. Tests: backend
  308, frontend 146, E2E 23; tried in the dev app (unknown email, then sharing with
  demo@demo.com as editor; that share was removed again). (68837fa, v0.0.14)

## 2026-10-09

- **Couple link on the canvas (D93)** — rings + wedding year (marriage), dashed line + heart
  (unmarried), struck-through rings (divorce / separation), tooltip with date and place;
  `PARTNER_GAP` 24 → 56; graph endpoint returns `end_reason` and `place` for partnerships.
  Demo: +2 people (Лариса — divorced from Юрій; Ігор — Олена's unmarried partner) → 66; dev
  copies extended with `make seed`. Tests: backend graph + seed, frontend 145, E2E 23.
  (commit "Couple link on the tree"; seed run in production after deploy)
- **Production: demo copies extended** — v0.0.12 deployed (CI green incl. E2E); ran
  `python -m app.seed --all-users` in the backend pod: 5 users' copies 25 → 64 people, all 690
  portrait jobs succeeded, readyz 200. One demo copy whose owner account was deleted (no owner)
  stays at 25 — visible only in Admin → Trees; delete it there if not needed.
- **No overlapping cards on the canvas (D92)** — `canvas/overlap.ts` (`separate`) pushes
  overlapping cards apart left to right after saved offsets are applied; drawing only, offsets
  untouched. Found because the dev admin's demo copy had old drags that landed on new people
  (e.g. Stephen Tkachuk on Андрій Бондар). Frontend tests 143. (commit "Canvas: cards never overlap")
- **Bigger demo family (D91)** — 25 → 64 people, 5 → 7 generations (1830s–2010s), several root
  couples, side branches, 4 new places (Миргород, Коломия/Kolomea, Дніпро/Катеринослав,
  Winnipeg). The original 25 are unchanged. `make seed` extends existing copies (people in the
  trash are not brought back). Seed refactored into helpers (`_person_body`, `_relations`,
  `_places`, `_extend`); `complete_demo` returns `DemoUpdate(added, updated)`. E2E focus test
  now expects 7 cards around Emily. Tests: backend 307, E2E 23. Dev copies extended with
  `make seed`. (commit "Bigger demo family")
  - To update production copies after deploying: run `python -m app.seed --all-users` in the
    backend pod.
  - Copies with dragged cards (e.g. the dev admin's: 8 offsets) look tangled until "Reset
    layout".

## 2026-10-08

- **Deployed v0.0.11** — production ran migration 0008, `/api/readyz` 200; CI green
  including end-to-end tests (first time since 2026-10-07 afternoon).
- **"Import GEDCOM" next to "New tree"** (superadmins, like "New tree"): creates a tree named
  after the file and opens the preview; cancelling removes that tree; a refused file deletes it
  at once. Empty trees also offer "or import a GEDCOM file". (commit "Phase 9: GEDCOM import and integrity checks")
- **Phase 9 (parts 1–2): GEDCOM import and integrity checks** — backups are left to the
  infrastructure (owner's decision). D89, D90; migration 0008 (`gedcom_imports`,
  `integrity_runs`, `integrity_issues`).
  - GEDCOM: own reader (`app/importers/gedcom/`: encodings incl. ANSEL / cp1251, dates, names
    with patronymics), service `services/gedcom_import.py` (analyse → preview with duplicate
    candidates → confirm with merges → import in one transaction, savepoint per item → undo
    via trash), API `/trees/{id}/imports`, page `/trees/:id/import` ("Import GEDCOM" in the
    builder toolbar). Create services got `commit=False` (events, places, sources, citations).
  - Integrity: weekly worker job (Sun 04:23) + "Check now" on Admin → System status; issues
    listed with tree and file.
  - Tests: backend 306 passed (new: parser, import API, integrity), frontend 136, E2E 23
    (local). Verified in the dev app with a sample file. (commit "Phase 9: GEDCOM import and integrity checks")
- **Fix: tree download box moved to the top-right** — at the top-left it covered the spot where
  the E2E test (and users) start dragging the canvas; it was the last CI E2E failure. (75b8f97)
- **CI end-to-end tests fixed (config)** — CI E2E had failed since English became the default
  (7b3134f): the CI stack started without `DEFAULT_LANGUAGE=uk` / `DEMO_TREE_FOR_NEW_USERS=false`,
  which `make test-e2e` sets, so tests could not find the Ukrainian labels. Added both to the CI
  `.env`. (commit "Phase 9: GEDCOM import and integrity checks")
- **Tree export to PNG / PDF** — "Download: PNG | PDF" in the top-left corner of the tree canvas
  (view and builder). Whole tree with title, people count and date; current theme and style. New
  dependency `html-to-image` 1.11.11 (notices regenerated); own one-page PDF writer `lib/pdf.ts`.
  D88. Verified by downloading both from the local app (PNG 6858×3276, PDF on A2). (d8267da)
- **Added `plans/`** (this folder: README, roadmap, implementation overview, log) and `CLAUDE.md`
  telling every session to read and update it.

## 2026-10-07

- **Person delete in builder side panel** — red "Delete" next to Focus here / Open full page /
  Edit, opens the existing move-to-trash preview; only in Builder mode. (737cf47, v0.0.8)
- **Rename and delete trees from the list and the builder toolbar** — shared `TreeActions`
  component; deleting the open tree returns to the list. (737cf47)
- **Delete a tree from its card on the tree list.** (bdde67b, v0.0.7)
- **Tree deletion by tree admins; admin "Trees" tab** — list all trees (incl. deleted), delete,
  restore (`POST /admin/trees/{id}/restore`); demo copy restore refused when a newer one exists.
  D86. (b5c6ba7)
- **Production fix: media volume not writable** — `/api/readyz` returned 503 "storage root not
  writable"; csi-driver-nfs resets the volume root to 0755 on each mount and nginx has no fsGroup.
  Init container in backend/worker/nginx sets group 1000, mode 2775. Verified in prod: readyz 200.
  D87. (2c2dd89, v0.0.6)
- **Licence, footer, third-party notices, app version** — re-added after the revert, without the
  security-scan changes; version passed from the Deploy workflow into both images. D85. (b603610)
- **Revert of licence + security-scan changes** — the app stopped loading locally; reverted
  without touching CI / Argo commits. (93c568f)
- Earlier the same day: phases 1–8, tree layout and styles, themes, demo family, Helm/Argo deploy —
  see `git log` and `implementation.md`.

### Open after 2026-10-07

- Phase 9 waits for the go-ahead.
- Vite dev cache fix (see roadmap "Open issues") waits for the owner's OK.
