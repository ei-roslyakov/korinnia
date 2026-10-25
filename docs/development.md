# Development

**Prerequisites:** Docker with Docker Compose v2, and `make`. Node and Python are *not* needed on
the host — everything runs in containers. Optionally install [uv](https://docs.astral.sh/uv/) to run
backend tools directly.

## First start

1. `cp .env.example .env` (`make up` does this automatically if `.env` is missing).
2. `make up` builds the images and starts PostgreSQL, the backend (which applies migrations), the
   worker, the Vite dev server and nginx, then waits until they are healthy.
3. Open <http://localhost:8080> and sign in as **`admin@example.com` / `change-me-now-please`**
   (`SUPERADMIN_EMAIL` / `SUPERADMIN_PASSWORD` in `.env`, created on first start only).

Every new account gets its own copy of the demo family. `make seed` gives one to existing users and
brings older copies up to date without touching anything the owner changed or deleted.

## URLs

| What | URL |
|---|---|
| App (through nginx, hot reload) | http://localhost:8080 |
| API docs (Swagger UI) | http://localhost:8080/api/docs |
| Backend directly | http://localhost:8000 |
| Vite dev server directly | http://localhost:5173 |
| PostgreSQL | `localhost:5432` (user / password from `.env`) |

## Everyday commands

```bash
make help            # list all commands
make logs s=backend  # follow logs of one service
make test            # backend (pytest, separate korinnia_test DB) + frontend (Vitest)
make test-e2e        # Playwright on a throwaway production-build stack (your data is untouched)
make lint            # ruff, mypy, oxlint, prettier, tsc
make fmt             # auto-format everything
make migrate         # apply migrations manually
make revision m="add person table"   # autogenerate a migration
make seed            # demo family for every user who has none (safe to re-run)
make perf            # performance check on a large synthetic tree (PEOPLE=2000)
make notices         # regenerate third-party licence notices after dependency changes
make psql            # database shell
make down            # stop (volumes, i.e. your data, are kept)
```

`make lint` and `make test` reinstall frontend dependencies, which wipes Vite's pre-bundled cache;
run `docker compose restart frontend` afterwards or the tree canvas shows empty.

The pre-commit hooks are optional but recommended: `cd backend && uv run pre-commit install`.

## Conventions

- UI strings go into `frontend/src/i18n/locales/{en,uk,pl}.json`. E2E tests use the Ukrainian UI.
- Schema changes need an Alembic migration and an update to [data-schema.md](data-schema.md).
- Design decisions get the next D-number in [decisions.md](decisions.md).
- Changes visible to users get a "What's new" entry in
  `frontend/src/features/onboarding/changelog.ts`; changes to how the app is used also update the
  user guide (`frontend/src/features/help/guide.{en,uk}.md`, same sections — a test checks it).

## Troubleshooting

- **Port already in use:** change `HTTP_PORT` in `.env`, or stop whatever is using 5432, 8000 or 5173.
- **`make up` waits forever / a service is unhealthy:** check `make ps` and `make logs s=backend`.
  The backend only becomes healthy after migrations succeed.
- **Frontend dependencies changed:** `docker compose restart frontend` (runs `npm ci` on start).
- **Start from scratch (deletes all data):** `docker compose down -v`.
- **"Too many failed attempts":** sign-in is throttled for 15 minutes after 5 failed attempts per
  email (20 per IP).
- **Signed out right after signing in:** over plain HTTP, `COOKIE_SECURE` must be `false`.
- **Permission errors on the media volume:** containers run as uid 1000. Named volumes get the
  right ownership automatically; a bind mount must be writable by uid 1000.
