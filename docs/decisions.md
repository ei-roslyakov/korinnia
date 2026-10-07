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

## Phase 2: users, roles, administration

### D18. Session design: short access JWT + rotating refresh JWT, both in httpOnly cookies
- **Access token:** 15 minutes, cookie `korinnia_access`, `Path=/api`. Each request checks the user's `is_active` and `sessions_valid_after`, so deactivation works immediately rather than at expiry.
- **Refresh token:** 30 days, cookie `korinnia_refresh`, `Path=/api/v1/auth`, so it is never sent to other endpoints. Each refresh token has a server-side row (`refresh_tokens`), and tokens from one login share a `family_id`. Every refresh **rotates** the token. Replaying a rotated-out token more than 30 s after rotation is treated as theft and revokes the whole family. The 30 s grace window covers parallel tabs refreshing at the same moment; the frontend also deduplicates concurrent refreshes.
- **"Sign out everywhere":** `users.sessions_valid_after`. Tokens with an earlier `iat` are rejected, compared at second precision because JWT `iat` is whole seconds. Password change, password reset and deactivation set it, and the browser that changed the password gets a fresh session.
- **Cookies:** `SameSite=Lax`, `Secure` unless `COOKIE_SECURE=false`, and `httpOnly`, so JavaScript never sees a token.
- **Why not localStorage tokens:** they are readable by any injected script. httpOnly cookies plus CSRF protection are the safer combination for a browser-only app.

### D19. CSRF: double-submit cookie in a pure ASGI middleware
A readable `korinnia_csrf` cookie is set on the first response. Every non-GET request to `/api/` must echo it in `X-CSRF-Token`, which covers login too (login CSRF). It is implemented as a pure ASGI middleware, not `BaseHTTPMiddleware`, so large uploads stream through untouched.

### D20. Login throttling in PostgreSQL
Each attempt is stored in `login_attempts`. A login is refused with 429 and `Retry-After` when there are 5 failures per email or 20 per IP within 15 minutes, which also covers the 2FA step. A daily job deletes rows older than 30 days. Unknown emails still verify against a dummy hash, so response time doesn't reveal which emails exist.
**Known limitation:** the client IP comes from the proxy chain (`X-Forwarded-For`), and Uvicorn currently trusts all proxies. Restricting trusted proxies is part of phase 10 hardening. Per-email throttling is unaffected.

### D21. TOTP 2FA for every user, not only admins
The spec says "optional TOTP 2FA for admins". It is available to every user at no extra cost, and the UI recommends it to admins. The QR code is an SVG generated server-side with segno (pure Python), so no external QR service is used. Codes accept ±1 time step, and `totp_last_counter` rejects replays. Ten one-time recovery codes are stored as SHA-256 hashes. A superadmin (or `python -m app.cli disable-2fa`) can reset 2FA for a user who lost their device.
**Known limitation:** the TOTP secret is stored unencrypted in the database. Anyone with database access could generate codes, but they would still need the password. Revisit in phase 10 (encrypt with a key derived from `SECRET_KEY`).

### D22. No email sending; links are copied by administrators
Invitations (7 days) and password resets (24 h) are one-time links. The database stores only the SHA-256 of the token. Administrators copy the link from the UI and send it however the family communicates. This avoids SMTP configuration and a dependency on an email provider. There is no self-service "forgot password": the user asks an admin. An operator CLI (`python -m app.cli`) covers the case where the only admin is locked out.

### D23. Role model and authorization
- Roles are cumulative: viewer < contributor < editor < admin. A superadmin acts as admin in every tree.
- All tree endpoints use one dependency, `tree_access(min_role)`. Non-members get **404** so a tree's existence isn't revealed; members with too low a role get **403**.
- Only a superadmin creates or deletes trees. A tree admin manages members and can rename the tree.
- Safety rails: a tree keeps at least one active admin, the installation keeps at least one active superadmin, and you cannot deactivate, demote or delete yourself.
- "Add member" takes an email. An existing user is added directly; a new email creates an invitation. This gives tree admins one simple form, at the cost of revealing to a tree admin whether an email has an account. That is acceptable within a family.

### D24. Enumerations stored as VARCHAR + CHECK, not native PostgreSQL enums
Native enums are awkward to change in migrations, because values can't be removed or renamed inside a transaction. A text column with a named CHECK constraint is just as strict and readable by any tool. The helper is `app.models.base.text_enum()`.

### D25. Audit log design
`audit_log` is append-only and records `action`, `entity_type`, `entity_id`, `tree_id`, the user (with `user_label` preserved after the user is deleted) and the IP. `before`/`after` are JSONB containing only the changed fields. Secret fields (`password_hash`, `totp_secret`, token hashes) are never written. `tree_id` deliberately has no foreign key, so entries survive tree deletion. `created_at` defaults to `clock_timestamp()` rather than `now()`, which is fixed for the whole transaction, so entries written in one request keep their real order. Phase 3 builds full entity revisions with restore on top of this.

### D26. Deleting users
Deleting a user is a hard delete. Their memberships, sessions and recovery codes go with it, while audit entries and tree ownership are kept (`SET NULL`). The UI recommends deactivating instead. From phase 3, content authorship (`created_by`) is also `SET NULL`, so family data is never lost when an account is removed.

### D27. Test database isolation
Tests run against a real PostgreSQL. The schema is migrated once per session, and each test runs in an outer transaction with `join_transaction_mode="create_savepoint"`, so service-level `commit()` calls release savepoints and everything is rolled back afterwards. Coverage is measured with `concurrency = ["greenlet", "thread"]` because SQLAlchemy's async ORM runs inside greenlets; without it, coverage under-reports.

### D28. Separate image tags for dev builds
The dev override tags its images `korinnia/backend:dev` and `korinnia/nginx:dev`, so a production build (`:latest`, without test tools) can't overwrite the dev image or the other way round.

## Phase 3: core genealogical data

### D29. Partial dates: plain columns + a derived sort date
Each partial date (D2) is stored as columns `<prefix>_year`, `_month`, `_day`, `_precision`, `_end_year`, `_end_month`, `_end_day`, `_phrase`, plus `<prefix>_sort` (a real `date`, indexed) for ordering. SQLAlchemy maps them onto one `PartialDate` value object (`composite()`). The precision rules are strict: `exact` needs day and month, `between` needs an end that isn't before the start, and impossible dates such as 30 February are rejected. The API infers precision from the parts given. `_phrase` keeps the original wording ("Easter 1888", GEDCOM date phrases). JSON was considered and rejected: plain columns stay queryable (search by year) and can be read with any SQL tool.

### D30. Birth and death are Events, exposed as fields
They are stored as `events` of type `birth`/`death` with exactly one principal participant, so they get places, descriptions, sources and history like any other event. The API also exposes `birth` and `death` on the person: writing them creates, updates or removes the underlying event. At most one live birth and one live death per person, enforced in the service (`vital_exists`).

### D31. `is_living` defaults to "living" unless clearly dead
If the editor doesn't set it: a recorded death → not living; born more than 110 years ago → not living; otherwise **living**, including when the birth date is unknown. Wrongly hiding a dead ancestor in a share link is harmless; exposing a living person's details is not. Recording a death sets `is_living = false`.

### D32. Name search: stored transliteration + trigram index
`person_names.search_text` and `places.search_text` hold lower-cased, accent-free tokens **plus** the Ukrainian→Latin transliteration (official KMU 2010 system, including word-initial forms and "зг"→"zgh"). The query is normalised and transliterated the same way, so "kovalenko" finds "Коваленко" and "Ковал" finds "Kovalenko". PostgreSQL's `unaccent()` isn't immutable and so can't be indexed; doing it in Python keeps the index (`gin_trgm_ops`) usable for `ILIKE '%…%'`. A 4-digit query term matches birth/death years. Spellings that differ beyond transliteration (e.g. Polish "Kowalenko") are found by partial matches or stored as explicit name variants.

### D33. Hard errors vs. soft warnings
Structural impossibilities are **errors**: self-relations, cycles (recursive CTE over ancestors), duplicate links, a third biological parent, duplicate birth/death. Contradictory or implausible *dates* are only **warnings** (`{code, params}`), returned with the relationship and on every person. Sources often disagree and the archive must be able to record what they say. Warnings only fire when dates are *certainly* implausible given their precision; approximate dates get ±5 years of slack. Thresholds: parent younger than 12, mother older than 60, father older than 90, lifespan over 120, child born after the mother's death or more than ~10 months after the father's.

### D34. Revisions are full snapshots in the audit log
For genealogical entities, `audit_log.before/after` store the **complete** state:
- a person with all names and birth/death,
- an event with its participants,
- a relationship, or a place.
Restoring a revision (`POST /history/{id}/restore`) makes the entity equal to that entry's `after` and is itself recorded as a new revision, so a restore can be undone. Deleted entities are restored from the trash, not from history. Members with any role can read history (IP addresses only for tree admins). Editors restore.

### D35. Soft delete in batches; no permanent deletion yet
Deleting a person soft-deletes their relationships and the events in which they are the only participant. Shared events stay and the person is hidden from them. All rows share `deleted_batch_id` = the person's id, and the trash lists only these "roots". Restoring a root restores the batch; a relationship whose identical live copy was created in the meantime stays in the trash. A place cannot be deleted while live events or partnerships use it (`place_in_use`). Permanent purging is deliberately not offered (preservation first). It may come in phase 10, admin-only, if needed.

### D36. Event participants are synced in place
Replacing an ORM collection wholesale makes SQLAlchemy INSERT the new rows before DELETEing the old ones, which violates `UNIQUE(event_id, person_id)`. Participants are therefore diffed: existing rows keep their id with an updated role, new ones are added and missing ones removed.

### D37. Enumerations live in `app.core.enums`
They were in `app.models.enums`, but importing them from `app.core.dates` loaded the whole `app.models` package, which imports `app.core.dates`: a circular import that only worked when models happened to load first. Enums now live in a dependency-free module.

### D38. Partnership dates live on the partnership
A partnership carries its own start/end partial dates, place and end reason, so the family structure is complete without events. `marriage`/`divorce` events stay available for extra detail, such as a church wedding with witnesses, and may coexist.

### D39. Seed data goes through the services
`python -m app.seed` builds the demo family through the same services as the API, so it is validated, appears in the history, and its own test asserts that the family produces **no** plausibility warnings. It is idempotent: nothing happens while the demo tree exists.

### D40. End-to-end tests run on a throwaway stack
`make test-e2e` builds the **production** images, starts them as a separate Compose project (`korinnia-e2e`, port 8091), runs Playwright against them, then removes the project including its volumes. Tests always start from a clean database (bootstrapped superadmin, Ukrainian UI) and never write into the developer's own dev data. The earlier version ran against the dev stack, so it created test trees and users there and broke as soon as the admin changed their language. CI does the same thing against freshly built images.
