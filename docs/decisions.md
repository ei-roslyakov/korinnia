# Architecture decisions

A log of non-obvious decisions. Newest entries go at the bottom of each phase. Format: **context → decision → consequences**.

## Phase 1: scaffolding

### D1. UUID primary keys everywhere
A family archive will be exported, imported (GEDCOM), merged between trees and restored on other machines over decades. Sequential integer IDs collide between installations and leak record counts. **Decision:** every table uses a UUID primary key that the application generates. **Consequences:** IDs stay stable across export → import, and the offline archive can link records by ID. They are slightly larger than integers, which doesn't matter at this scale (thousands of people).

### D2. Genealogical dates are not SQL `date`s
Real-world dates are often partial or uncertain: "1890", "March 1902", "about 1850", "before 1901", "between 1914 and 1918". A SQL `date` cannot represent these without inventing precision. **Decision (applies from phase 3):** store `year`, `month` and `day` as nullable integers plus `date_precision` (`exact | month | year | approx | before | after | between | unknown`), with a second set of fields for the end of a range, and a derived `sort_date` for ordering. **Consequences:** nothing is invented, and GEDCOM date phrases map losslessly. Queries sort by `sort_date`.

### D3. Local filesystem storage only (no MinIO / S3)
The spec proposed an S3-compatible backend (MinIO). MinIO stopped publishing community Docker images in 2025, and the owner wants data kept locally on a volume that is a Kubernetes PVC in production. **Decision:** one `LocalStorage` implementation behind the `Storage` interface (`app/storage/`). Files are stored at `/data/media/<key>` as plain files, with no proprietary layout. **Consequences:**
- The archive is readable with `ls` and any file manager. Backups are a plain `tar`.
- Backend, worker and nginx all mount the same volume. On Kubernetes this needs either a `ReadWriteMany` PVC (e.g. NFS / CephFS / Longhorn RWX) or all three containers in one pod / on one node with a `ReadWriteOnce` PVC. Set `fsGroup: 1000` so the non-root containers (uid 1000) can write.
- Off-site copies (phase 9) are done by the backup job, not by the storage layer.
- The `Storage` interface keeps another backend possible later without touching business code.

### D4. Storage write rules
**Decision:** each write computes SHA-256 while streaming, writes to a temp file in the same directory, `fsync`s it, then renames it into place atomically. `put()` refuses to overwrite an existing key unless `overwrite=True` is passed, which only derived files (thumbnails, web versions) may do. Keys are restricted to `[A-Za-z0-9._-/]`, and `..`, empty segments and escapes through symlinks are rejected. **Consequences:** originals cannot be silently replaced, a crash never leaves a half-written original, and integrity checks have a reference hash. Human-readable original filenames are stored in the database, not in the key.

### D5. procrastinate for background jobs, schema via Alembic
The spec requires a Postgres-backed queue (no Redis). **Decision:** procrastinate. Its schema SQL is **vendored** into `alembic/versions/sql/procrastinate_<version>_schema.sql` and applied by the baseline migration, so migrations stay reproducible no matter which library version is installed. The SQL runs on a raw DB-API cursor without parameters, because it contains literal `%` characters. **Upgrading procrastinate:** add a new Alembic migration that applies the library's `sql/migrations/*.sql` files for the version range. Never edit the baseline. **Worker:** `python -m app.jobs.worker` (not the `procrastinate` CLI) so it shares the API's JSON logging and imports `app` from the working directory. Queues are `default`, `media` and `maintenance`.

### D6. One database driver: psycopg 3
SQLAlchemy (async) and procrastinate both use psycopg 3, so there is one driver to maintain instead of asyncpg plus psycopg.

### D7. Only the backend runs migrations
The backend runs `alembic upgrade head` before starting Uvicorn. The worker `depends_on` the backend being healthy, so it never starts against an unmigrated schema. With more than one backend replica (e.g. Kubernetes), migrations should move to an init container or a one-off Job (`docker-entrypoint.sh migrate`).

### D8. Health probes outside `/api/v1`
`/healthz` (liveness, no dependencies) and `/readyz` (database `SELECT 1` and storage writability) are served at the root for container and Kubernetes probes, and also under `/api/` so they can be reached through nginx. Readiness returns 503 with a JSON body that lists which check failed.

### D9. No TLS in the application
**Decision:** nginx only speaks plain HTTP. TLS and HSTS are handled by the ingress or load balancer in front of it, as the owner requested; certbot was removed. nginx passes the incoming `X-Forwarded-Proto` through, and Uvicorn trusts proxy headers.

### D10. nginx image builds the frontend; dev proxies to Vite
`deploy/nginx/Dockerfile` has three stages: `frontend-build` (Node), `base` (nginx with config) and `prod` (base plus static files). The dev override uses the `base` target and mounts `frontend-dev.conf`, which proxies `/` to the Vite dev server with HMR. So <http://localhost:8080> is the single entry point in both modes, and `/api` routing is identical.

### D11. gzip only, no brotli (for now)
The official nginx image has no brotli module, and third-party images with brotli are not mainstream enough for a decades-long project. **Decision:** dynamic gzip plus `gzip_static` with `.gz` files pre-compressed at build time. **Revisit** if the official image adds brotli.

### D12. Content-Security-Policy
The production policy is strict: `script-src 'self'`, no inline scripts, and images limited to self plus OpenStreetMap tiles (for the map view). Two locations have their own scoped policy: `/api/docs` (Swagger UI loads assets from jsDelivr; the docs are disabled in production) and the dev-only Vite proxy (inline React Refresh preamble, WebSocket HMR). Note that nginx's `add_header` in a `location` replaces inherited headers, so every location that sets headers re-includes `snippets/security-headers.conf`.

### D13. Media will be served via `X-Accel-Redirect`
nginx mounts the media volume read-only and exposes an `internal` location, `/_media/`. From phase 6 the backend checks permissions, then responds with `X-Accel-Redirect: /_media/<key>`. Large videos are streamed by nginx with range support, and no URL is reachable without authorisation. This replaces the "presigned URL" option from the spec, which only applies to S3.

### D14. Destructive DB tests only run against `*_test` databases
`tests/test_db.py` migrates up, down and up again. To protect real family data, it skips itself unless the database name ends in `_test`. `make test-backend` creates and uses `korinnia_test`.

### D15. Frontend dependency choices
- React Router (library mode, `<BrowserRouter>`) for routing. It wasn't in the spec, but an SPA needs a router and React Router is the mainstream choice.
- i18n detection only reads the user's explicit choice from `localStorage`. Otherwise the UI is Ukrainian, the stated default, rather than the browser's language.
- Vitest runs without globals, so Testing Library's `cleanup` is registered explicitly in `src/test/setup.ts`.

### D16. Non-root containers, uid 1000
The backend and worker run as `korinnia` (uid / gid 1000). `/data/media` is created in the image with that owner, so a new named volume (or a PVC with `fsGroup: 1000`) is writable.

### D17. PostgreSQL data checksums
The database cluster is initialised with `--data-checksums` so silent on-disk corruption is detected. This fits the preservation mission, and the cost is negligible.
