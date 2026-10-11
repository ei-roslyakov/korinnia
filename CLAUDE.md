# Korinnia — notes for AI sessions

Self-hosted family archive and interactive family tree (FastAPI + PostgreSQL + React).

## Start here

- Read `plans/roadmap.md` (where the project stands, what is next, open issues) and the top of
  `plans/log.md` before starting work. `plans/implementation.md` describes how everything is built.

## Keep the plans current (required)

- After finishing any task, add a short dated entry to the top of `plans/log.md`: what changed,
  why, the commit hash if committed, and anything left open.
- If the task finishes a feature, adds an idea, or uncovers a problem, update `plans/roadmap.md` in
  the same change. Structural changes also go into `plans/implementation.md`.
- When a change is visible to users, add a dated entry (en / uk / pl) at the top of
  `frontend/src/features/onboarding/changelog.ts` — users see it in "What's new" at sign-in.
  If it changes how the app is used, check the welcome guide (`welcome.*` strings) too.
- Keep the existing docs current too: README feature statuses (✅ / 🚧 / 📋), a new D-number in
  `docs/decisions.md` for design decisions, `docs/data-schema.md` for schema changes.

## Working rules

- Commit and push only when asked; the owner usually checks locally first. Pushing to `main`
  deploys to production (korinnia.app) through the Deploy workflow and Argo CD.
- Before reporting work as done: `make lint`, `make test` (and `make test-e2e` for UI flows).
  These commands wipe Vite's dev cache — run `docker compose restart frontend` afterwards or the
  tree canvas shows empty in the local app.
- UI strings go into `en.json`, `uk.json` and `pl.json`; E2E tests use the Ukrainian UI.
- Do not re-apply the reverted security-scan changes (uv `exclude-newer`, nginx `/__vite_hmr`,
  E2E RegExp edits) without asking.
