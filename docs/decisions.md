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
- Only a superadmin creates trees. A tree admin manages members, can rename the tree and can delete it (see D86).
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

## Phase 4: tree canvas, person page, search

### D41. Layout: ELK layered with "family" junction nodes
Every couple, or set of co-parents, becomes a small junction node: parent → family → child. ELK's layered algorithm (direction DOWN, network-simplex placement, model order preserved) then puts each generation on its own row, keeps partners next to their shared junction, and handles remarriages, half-siblings and pedigree collapse, none of which a strict tree layout can draw. Childless couples still get a junction so partners stay together. Non-biological child links are drawn dashed.

### D42. ELK runs in its official Web Worker
Laying out thousands of nodes can take hundreds of milliseconds, so it must not block the UI. elkjs's own worker script (`elk-worker.min.js`) is loaded as a same-origin asset (`?url` import), which the strict CSP allows without `unsafe-eval`. Running `elk.bundled.js` inside our own worker does **not** work: elkjs detects the worker context and installs itself as the message handler. The CommonJS default export also differs between Vite dev, the Rolldown production build and Vitest, so `resolveElkConstructor()` normalises it. Results are cached with TanStack Query, keyed by graph version and the set of shown people.

### D43. Focus mode by default for large trees
Trees with more than 150 people open on the root ancestor with the most descendants, showing 3 generations up and down; "Whole tree" shows everyone. Focus includes ancestors, descendants, their partners, and the person's siblings. Cards show ▲/▼ when relatives are hidden. Focus, selected person and depth live in the URL, so views can be shared and survive reloads.

### D44. Rendering 2,000+ people
React Flow renders only the nodes inside the viewport (`onlyRenderVisibleElements`). Nodes aren't draggable in view mode, and custom node components are memoised. With the demo data plus a synthetic 2,000-person graph, layout and render stay responsive. The formal performance test is in phase 10.

### D45. Search covers names, places and years
Each query term must match a name variant (with transliteration), or the current or historical name of a place where one of the person's events happened. A 4-digit term matches birth/death years. The search box is an accessible combobox (arrow keys, Enter, Escape). The result is centred and opened, and the focus moves to it if it was hidden.

### D46. Person view is one component in two places
The same `PersonView` renders inside the canvas side panel (full width on phones) and on the stand-alone page `/trees/:id/people/:personId`, which can be linked to and printed. Markdown is rendered with react-markdown + GFM. Raw HTML is never rendered, and links open in a new tab with `rel="noopener noreferrer nofollow"`. Data-quality warnings are shown to editors and above only.

## Phase 5: builder (editing UI)

### D47. Adding a relative is one atomic request
`POST /persons` accepts an optional `relative` (`parent` / `child` / `partner` / `sibling`, with link type, union type and an optional second parent). The person and all links are created inside one savepoint (`session.begin_nested()`), so a validation error, such as a third biological parent or a cycle, leaves nothing behind. Sibling = same parents as the relative; it requires at least one parent.

### D48. Manual layout = offsets, not coordinates
Dragging a card stores `(dx, dy)` relative to the automatically computed position (`layout_offsets` table, one row per person). Offsets keep making sense in focus mode and after the family grows; absolute coordinates would not. Family junctions are re-centred between moved parents and children. Offsets are presentation, not family data, so they're not written to the audit log. "Reset layout" deletes the tree's offsets.

### D49. Layout keyed by structure; never unmount the canvas on refresh
The ELK result is cached under a key derived only from who is shown and how they are linked. Edits to names or dates, drags, and saved offsets therefore never trigger a re-layout. When the structure does change, the previous layout stays on screen (`keepPreviousData`) until the new one is ready, and the view is only re-fitted on first load or when entering/leaving focus mode. Before this, a background refresh (another editor's change) unmounted the canvas and re-fitted the view under the user's cursor.

### D50. Biography drafts live in the browser
Unsaved Markdown (biography, notes for descendants) is written to `localStorage` per person and field, 0.8 s after typing stops. If a newer draft exists when the editor opens, it is offered for restore. Drafts are a per-user convenience: they never reach the server, other users, or the archive. Saving clears them.

### D51. CSRF token race on first load (bug fix)
On a fresh page, several requests without a CSRF cookie each received a different server-minted token; only the last `Set-Cookie` survived, so the login could send a stale token and fail with "session expired". The client now (a) makes every request wait for one shared `/auth/csrf` fetch when the cookie is missing, and (b) always sends the current cookie value. Covered by a unit test.

### D52. Deleting from the editor must not depend on the dialog
After a delete, the shared cache refreshed the deleted person (404). That replaced the editor with an error and unmounted the dialog before its "navigate back" callback ran. The deleted person's queries are now removed instead of refetched, and navigation uses `mutateAsync`.

### D53. Known limitation: spouses are not always side by side (resolved by D74)
ELK's layered algorithm keeps generations on rows, but its crossing minimisation sometimes separates partners (e.g. in the demo tree, Andrii and Oksana are several cards apart). Users can drag cards (D48). A layout that groups couples (compound nodes or a genealogy-specific ordering pass) is a candidate improvement for phase 10.

## Phase 6: media

### D54. Storage layout: originals vs. derived files
- **Originals:** `originals/<tree>/<media>/<ascii-name.ext>`. The bytes are exactly as uploaded and never modified; the SHA-256 is stored in the database.
- **Derived files:** `derived/<tree>/<media>/{web.webp, thumb.webp, web.mp4, web.mp3}`, and portraits at `avatars/<tree>/<person>/<hash>.webp`.

Derived files can be deleted and regenerated at any time (`POST /media/{id}/reprocess`). Backups must contain the originals; the derived files are a convenience. The original file name (any script) is kept in the database. The storage name is a transliterated ASCII version, so the archive stays readable on any filesystem.

### D55. Content-based type detection and an allow-list
The type comes from the file's magic bytes (`filetype`), never from its name. Allowed: common image formats including HEIC/HEIF, PDF, common audio and video formats, DOCX/ODT/DOC/RTF, and UTF-8 text by extension. HTML, SVG, executables and unknown binaries are rejected with 415, so nothing uploaded can run script in a viewer's browser. Size limit: `MAX_UPLOAD_SIZE_MB`, enforced by both nginx and the API (413). Identical files in a tree are detected by SHA-256 (409 `duplicate_media`, with the existing id), and the UI offers to link the existing file.

### D56. Processing in the worker, never in the request
An upload stores the original, records the item as `pending` and enqueues `media.process` (procrastinate, PostgreSQL). The worker generates the derivatives:
- **Photos and scans:** Pillow, EXIF-rotated; web version ≤ 2048 px and thumbnail ≤ 480 px, both WebP.
- **Video:** a poster frame plus H.264/AAC MP4 (≤ 1280 px wide, faststart) via ffmpeg.
- **Audio:** an MP3 only when browsers can't play the original.
- **PDF:** a first-page thumbnail via poppler.

Failures are stored on the item (`failed` plus the reason) instead of being retried endlessly, and can be retried from the UI. A sweep every 30 minutes re-queues items stuck in `pending`, for example when enqueueing failed. The API opens the job queue in its lifespan only to enqueue.

### D57. Files are served by nginx after an API permission check
`GET /api/v1/trees/{t}/media/{m}/file/{original|web|thumb}` checks tree membership, then answers with `X-Accel-Redirect: /_media/<key>`. nginx streams the file from its read-only mount of the media volume, with range requests for seeking in video and no Python in the data path. `/_media/` is `internal` and can't be requested directly. Without nginx (tests, `MEDIA_X_ACCEL=false`) the API serves files itself.
**Bug found by E2E:** `mkstemp` creates files with mode 0600, so nginx, running as a different user, got 403 for every file. Stored files are now 0644 inside the volume; access control is entirely the API's job (D57).

### D58. Face tags and portraits
`media_persons` links a person to an item, with an optional region `{x, y, w, h}` given as fractions of the image, so it is independent of resolution. The person's gallery order is `sort_order` on the same row. The portrait is `persons.primary_photo_id` plus a square `primary_photo_crop`, and the worker renders `avatars/...webp` (400×400). Until it exists, the item thumbnail is used and `portrait_pending` tells the UI to poll briefly. The first photo uploaded for a person becomes their portrait automatically. Removing the person's tag from the portrait photo clears the portrait.

### D59. Uploads use XMLHttpRequest
`fetch` can't report upload progress, so uploads go through XHR, with the same CSRF header and cookies as every other request. Each file is uploaded and processed independently, so one failure (too large, unsupported, duplicate) doesn't block the rest.

## Phase 7: sources, stories and collaboration

### D60. Citations point at facts through (entity_type, entity_id)
A citation can support a person (or one of their fields, e.g. `occupation`), a name, an event, a parent–child link, a partnership or a media item. Instead of six nullable foreign keys, `citations` stores `entity_type` + `entity_id` (+ optional `field`), and the service checks that the target exists in the same tree. When a fact is deleted its citations stay in the database but drop off the person page; restoring the fact brings them back. Comments and edit suggestions use the same pattern.

### D61. No unique constraint on citations
A database constraint on (source, target, field, page) broke "delete, then cite again" because the soft-deleted row still counted, and PostgreSQL treats NULLs as distinct, so it missed real duplicates. The service rejects a live duplicate with `409 citation_exists` (`IS NOT DISTINCT FROM` comparison) instead. Deleting a source moves it to the trash together with its citations in one batch.

### D62. Source search uses a transliterated `search_text`
Source titles are often in Cyrillic, Polish or Latin. As for people (D32), each source has a `search_text` column (title, author, archive and reference, plus KMU 2010 transliteration) with a trigram index, so "metryka" finds "Метрика".

### D63. Permission model for collaboration
- **Viewer:** reads published stories, citations, comments and research questions. Viewers are often relatives who only browse, so they do not write.
- **Contributor:** writes comments and research questions, writes stories (always saved as draft and submitted for review), and suggests edits to people and events. Contributors see only their own suggestions and their own unpublished stories, cannot change genealogical data directly, and can open the data-quality panel to find research to-dos.
- **Editor / admin:** edit everything directly, publish or return stories (with a comment), approve or reject suggestions, delete any comment or question, and see the moderation queue.

Authors can edit their own comments; a comment on a draft story is visible only to people who can see that story.

### D64. Approving a suggestion goes through the normal update path
A suggestion stores only the proposed values (`patch`) for an allow-listed set of fields; the moderation page shows them next to the current values. Approval calls the same `update_person` / `update_event` service as the editor UI, acting as the reviewer, so validation, warnings, search indexing and the audit log all apply unchanged. A suggestion can be reviewed once (`409 suggestion_already_reviewed`).

### D65. Data quality is computed on request
The data-quality panel (people without a birth record, photo or source; date problems; open questions) is computed by a few aggregate queries when the page is opened instead of being stored. At the target scale (≤ 2,000 people) this takes milliseconds and can never be stale.

### D66. Canvas nodes declare their size (bug fix)
E2E runs showed an intermittently blank tree after adding a person: React Flow hides a node (`visibility: hidden`) until it has measured it, and a rebuilt node array could lose the measurements without triggering a new measurement. Person and family nodes now pass `initialWidth` / `initialHeight` (their sizes are fixed anyway), so they are always visible.

### D67. Dialogs are never nested in the DOM
"Create a new source" opened from the citation dialog is rendered next to it, not inside it. Nested native modal dialogs make the outer one inert while the inner one is open; the E2E test caught input landing in the wrong dialog.

## Phase 8: map, timeline, relationship calculator, statistics, on this day

### D68. One loader for all dated facts
Timeline, map and "on this day" share `services/genealogy/facts.py`, which turns the tree into a list of *facts*: every live event, plus the start and end of each partnership. Marriages are usually recorded on the partnership (start date and place) rather than as a separate event, so without this they would be missing from all three views. If a marriage or divorce *event* exists for the same couple, it wins and the partnership fact is dropped, so nothing appears twice. A partnership that ended by death adds no fact, because the death is already one.

Facts are loaded in a fixed number of queries and filtered in Python. At the target scale (≤ 2,000 people, a few thousand events) that is milliseconds and keeps the three views consistent.

### D69. "On this day" uses exact dates only
Only facts with precision `exact` (day, month and year known) produce anniversaries; "about 1850" or "May 1902" would give false dates. 29 February falls on 28 February in common years. The client sends its own local date, so the result follows the viewer's calendar day rather than the server's time zone. Dates are treated as Gregorian; old Julian-calendar records should be entered converted, with the original wording in the date phrase.

### D70. Map points: a precise spot beats the place
A fact appears at the event's own coordinates when it has them (a grave's GPS pin) and otherwise at its place's coordinates. Facts at the same coordinates (5 decimal places, about 1 m) are grouped into one point. Facts whose place has no coordinates are counted and their places listed, so editors know what to complete. A list of places next to the map makes it usable by keyboard and screen readers, since Leaflet markers are not focusable. Leaflet and the map page are loaded only when the map is opened.

### D71. Kinship is computed as structure on the server and named on the client
The server finds the relationship as structure:
- **same person** or **partners**;
- **blood:** the closest common ancestor(s) by the fewest total steps (breadth-first over all parent links), giving `up`/`down` generations. Half relations are flagged when the two branch children each have two known parents and share exactly one. Non-biological links (adoptive, step, foster, unknown) are flagged rather than hidden;
- **in-law:** one partnership at either end (b is a blood relative of a's partner, or the partner of a's blood relative), choosing the closest;
- **distant:** any other chain of parent / child / partner links (breadth-first), returned as a path;
- **none.**

The word is chosen in the browser by a small generator per language (`features/insights/kinship.ts`). The vocabularies are not translations of each other:
- **Ukrainian** numbers collateral lines with "-юрідний" (двоюрідний дядько, троюрідний дід) and names in-laws by the speaker's sex (тесть / свекор, шурин / дівер).
- **English** counts cousins and "removed" generations.
- **Polish** uses descriptive forms beyond uncles and nephews (brat dziadka, wnuk siostry, kuzyn 2. stopnia).

When a person's gender is unknown both forms are shown ("брат / сестра"). The path and common ancestors are always shown as well, so the answer can be checked against the tree.

### D72. Statistics group spellings across scripts
Surnames and first names are grouped by their KMU 2010 transliteration (the same normalisation used by search), so "Коваленко" and "Kovalenko" count as one surname, shown under the most common spelling with the others as variants. Each person counts once per surname. "Generations" is the longest parent → child line. Ages and the average lifespan use only birth and death dates with exact, month or year precision, and ignore implausible values (< 0 or > 125 years).

### D73. Locale parity is tested
A unit test checks that `uk`, `en` and `pl` have the same keys (plural suffixes folded) and that every pluralised key has all the plural forms its language needs (`one`/`few`/`many`/`other` for Ukrainian and Polish).

### D74. Generation rows and couple units (replaces D53)
ELK's own layering put people on rows by longest path, so in-laws without recorded parents drifted up to the top, and crossing minimisation separated partners. The layout now works in three steps:
1. **Generation per person.** It is propagated breadth-first through each connected group: a child is one row below a parent, and partners share a row. Afterwards every child is pushed below all of its parents, so links always point down even in unusual data (e.g. a marriage into an older generation).
2. **Couple units.** Partners on the same row are merged into one *unit*, a block ELK cannot split. A person with several partners stands between them where possible. Each unit has fixed ports: one on top of every member, and one at the bottom per family it heads (between the partners). ELK uses interactive layering with the generation as the row, orders units to minimise crossings, and centres children under the parents' port.
3. **Placement.** Units are expanded back into cards, and each family junction is placed under its port, halfway to the next row.

Connectors are drawn as Bézier curves (parent → junction → child) instead of right-angled steps.

### D75. Cards move sideways only (replaced by D83)
Manual nudges change only the horizontal position, so dragging can never break the generation rows. The vertical part of offsets saved before this change is ignored rather than deleted; "Reset layout" removes offsets completely.

### D76. The tree grows upwards
Like a real tree, the oldest generation is at the bottom and descendants branch out above. ELK still lays out top-down; the rows are mirrored afterwards, and links leave a card from the top (to the person's own family) and arrive at the bottom (from the parents). Connectors are brown branches whose thickness decreases with the generation, so they are thickest at the root. A decorative ground strip sits under the oldest generation, with a trunk and roots under each founding couple that has children. It is purely visual: not focusable, ignores the pointer, and transparent in the minimap. Builder "+" buttons follow the direction: "add parent" is below a card, "add child" above it.

### D77. Themes are CSS variables
The UI uses a small palette: `bark` (neutrals), `leaf` (accent), `surface` (cards), `on-leaf` (text on accent backgrounds) and a few status colours (green, red, amber, sky, rose, violet, stone). Tailwind maps these to CSS variables (`@theme inline`), and each theme (`light`, `dark`, `sepia` "archive") only redefines the variables under `html[data-theme=…]`. In the dark theme the status colours are flipped (dark tints, light text), and the accent is a brighter green with dark text on it, so buttons and links both keep readable contrast. The tree canvas (sky gradient, branches, soil) and React Flow's controls also follow the theme, and map tiles are darkened in the dark theme.

The choice ("system" by default, which follows `prefers-color-scheme`) is kept in `localStorage` and applied before the first render, so pages never flash in the wrong colours. It is per device on purpose: one may want the dark theme on a phone and the light one on a desktop.

### D78. Every user gets their own demo family
A new account (created by an admin, through an invitation, or as the bootstrap superadmin) gets its own editable copy of the fictional demo family, so people can explore and practise without touching the real archive. The copy is built by a background job (`demo.create_for_user`) after the user is committed. `make seed` (`python -m app.seed --all-users`) gives a copy to existing users and fills in missing biographies and portraits in older copies, never overwriting anything a user has written. `DEMO_TREE_FOR_NEW_USERS=false` turns this off for a production archive (the E2E stack does so too).

Demo trees carry `is_demo`, and a partial unique index allows only one live copy per owner, so a job and a manual seed running at the same time cannot create two. A copy is an ordinary tree the user administers: they can edit it, share it or delete it. Superadmins, who otherwise see every tree, do not see other people's demo copies in their list.

### D79. Illustrated portraits for invented people
The demo people are fictional, so there are no photographs of them, and photo-realistic fakes of non-existent people could be mistaken for genuine records in a family archive. Real archival photos are no better: they show real people who would be presented as invented relatives. So each person gets a detailed *drawn* portrait styled as a photograph of their era:
- **Before 1915:** a sepia cabinet card.
- **1915–1959:** a faded black-and-white print.
- **From 1960:** a yellowed colour print.

Each portrait has a shaded face with eyes, brows, nose and mouth, age marks (wrinkles, greying), hair styles, moustaches, and clothing of the time: embroidered shirts, coral beads, headscarves, suits and ties. Every portrait carries the name, years and an "ілюстрація" mark.

Portraits are drawn deterministically with Pillow (supersampled, DejaVu fonts for Cyrillic) and stored through the normal upload path, so they get originals with SHA-256, thumbnails and a face-cropped card portrait like any uploaded photo. `PORTRAIT_VERSION` is part of the file name. When the drawing improves, `make seed` redraws generated portraits that are still in use and moves the old ones to the trash. A photo a user uploaded or chose instead is never touched.

### D80. X-Accel-Redirect only for requests that came through nginx (bug fix)
Opening the app on the Vite dev server (`:5173`) showed every image broken: Vite proxies `/api` straight to the backend, which answered file requests with an empty body and `X-Accel-Redirect`, a header only nginx understands. nginx now adds `X-Media-Accel: 1` to everything it proxies to the API (overwriting any client value), and the backend hands files over only when that header is present. Otherwise (Vite, direct `:8000`, tests) it streams the file itself. Production behaviour is unchanged.

### D81. English by default, configurable per installation
`DEFAULT_LANGUAGE` (default `en`) sets the interface language for visitors who have not chosen one and the starting preference of new accounts. `/api/v1/meta` exposes it, so the frontend can switch to it on the first visit. An explicit choice wins over the default: the header switcher (remembered in the browser and, for signed-in users, in the profile). The end-to-end stack runs with `DEFAULT_LANGUAGE=uk`, because its tests are written against the Ukrainian interface.

### D82. Visual polish without new dependencies (except fonts)
- **Fonts:** Lora (headings) and Inter (text) are self-hosted from `@fontsource-variable`. They were named in CSS before but never loaded, so browsers fell back to whatever was installed. The Latin and Cyrillic subsets are split by `unicode-range`, so a page downloads only what it uses. The CSP (`font-src 'self'`) needs no change.
- **Tree:** cards carry a gender accent, † and a hover preview. Hovering or selecting a person highlights their line: ancestors, descendants and partners (`lineage()` in `familyGraph.ts`). Each row is labelled with its generation (Roman numerals, counted from the oldest) and the decade of its median birth year.
- **Overviews come from the API:** the tree list's portraits, people count and years covered (three grouped queries for all trees), and each story's cover thumbnail and reading time (180 words per minute).
- **Historical context on the timeline** is a static list in the frontend (`features/insights/history.ts`), shown only within the years the family's facts cover. It is context, not data, so it is never stored or exported.
- **Feedback:** toasts (`useToast`, polite live region) replace inline "saved" messages; loading placeholders replace spinners where the page shape is known; the side panel and toasts animate only with `motion-safe`.

### D83. Dragging moves a whole branch, in any direction (replaces D75)
Users wanted to rearrange the tree freely, so cards move vertically again and stored vertical offsets apply again. Dragging a card moves its branch with it: the person, their partners, and all descendants with the descendants' partners and co-parents (`branch()` in `familyGraph.ts`). A family can therefore be moved aside as a unit without breaking its shape. Holding Alt moves only the one card. One drag is saved in a single request (`PUT /layout-offsets` with all moved cards; all or nothing), so moving a large branch is one transaction rather than one per card. "Reset layout" still restores the automatic layout.

### D84. Tree styles are decoration over the same layout
"Simple", "Oak" and "Spring" change only how the tree is drawn, never where people are: the same layout, cards and links. Oak adds a crown node (a soft, blurred cluster of leaf circles behind the generations above the founders) and a tapered bark trunk from the ground to each founding couple's knot. Its links are custom `branch` edges: filled outlines around a curve that rises from the base, sweeps sideways and bends up into the tip (`branchPath.ts`). They taper from the older end to the younger, and the thickness carries on through each knot (parent → knot from width(rank) to width(rank + ½), knot → child on to width(rank + 1)), so the tree thins steadily from trunk to crown. Longer branches carry small twigs with leaves, and a faint highlight gives a bark sheen. Spring uses the same tapered branches, thinner and with lighter leaves, plus blossoms on the two or three youngest generations. Both styles put leafy twigs along every branch (one per ~70–80 px, at least one per branch) and a fan of leaves around each family knot. Decorations are generated from a seeded pseudo-random sequence, so a tree looks the same every time, and use the theme's leaf and branch colours. They sit below the links (negative z-index), ignore the pointer and are transparent in the minimap.

Generation labels, branch thickness and blossoms come from the automatic layout's rows, not from where cards were dragged, so moving cards by hand never changes anyone's generation.

### D85. Licence notice and the visible app version
Korinnia is proprietary, all rights reserved (`LICENSE`). The footer shows the copyright, the release version and a link to the open-source licences the app bundles (`frontend/public/third-party-notices.txt`, regenerated with `make notices`).

The version comes from the Deploy workflow: it passes `APP_VERSION` as a build argument to both images. The backend reports it in `/api/v1/meta`; the frontend bakes it in at build time (`VITE_APP_VERSION`) and shows it as e.g. "v0.0.4". The argument sits late in each Dockerfile, so it never invalidates the dependency layers. Local and CI builds show "dev".

### D86. Tree admins delete trees; superadmins see and restore every tree

A tree admin can now delete their tree from its settings; before, only a superadmin could. Deleting stays a soft delete (`deleted_at`): the tree disappears for every member but nothing is destroyed, which is what makes it safe to hand to tree admins. The admin panel has a Trees tab (`GET /admin/trees`) listing every tree on the instance, including other users' demo copies that the superadmin's own tree list hides, with owner, people and member counts, and a switch to deleted trees. A superadmin can delete any tree there and restore a deleted one (`POST /admin/trees/{id}/restore`, audited as `tree.restore`). A deleted demo copy cannot be restored while its owner already has a newer live one (`409 demo_tree_exists`), because only one live demo per owner is allowed.

### D87. The chart repairs the media volume's top folder before each pod starts

On the cluster the media volume is an NFS PVC from csi-driver-nfs with `mountPermissions: "0755"`, which the driver re-applies to the volume's top folder on every mount. The nginx pod has no `fsGroup`, so after it mounted, `/data/media` was left `root:1000 0755` and the app (uid 1000) could no longer write there: `/api/readyz` failed with "storage root not writable", although uploads into the existing `originals/`, `derived/` and `avatars/` folders still worked. Each pod that mounts the volume (backend, worker, nginx) now runs a tiny root init container that sets the top folder to group 1000 and mode `2775`. That touches one directory instead of a recursive `fsGroup` change across all media, and works whichever pod mounts last. It requires an NFS export without `root_squash`, which this one is (the folder's group was already changed by root). `persistence.fixPermissions: false` turns it off.

### D88. Tree export to PNG / PDF happens in the browser

The tree view is exported where it is drawn: `html-to-image` (MIT, pinned to 1.11.11, the version React Flow's own export example uses) renders the canvas DOM into an image, so the picture matches the screen exactly (theme, tree style, portraits, the user's dragged layout) and the server needs no headless browser. During an export the canvas renders every card (viewport culling off), clears hover / selection highlights and leaves out the "+" buttons; the theme's sky-to-meadow gradient is painted underneath and the tree's name, people count and date go on top. Small trees come out at 3× resolution; big ones are scaled down to stay within browser canvas limits (14,000 px per side, 100 M pixels). The PDF is written by a few lines of our own (`lib/pdf.ts`): the JPEG goes in unchanged on one A4 / A3 / A2 page chosen by size, in the image's orientation, which avoids a large PDF library. Text in the PDF is part of the image (not selectable); a vector or multi-page "family book" PDF stays in phase 11.

## Phase 9: GEDCOM import and integrity checks

### D89. GEDCOM import: our own reader, a preview first, one transaction, undo via the trash

GEDCOM is read by a small reader of our own (`app/importers/gedcom/`) rather than a library: it keeps encodings and the mapping to our model under our control, avoids a GPL dependency (python-gedcom is GPL-2.0), and the format is simple. It handles UTF-8 / UTF-16 (with or without a byte-order mark), ANSEL and Windows code pages (a file that is valid UTF-8 is read as UTF-8 whatever it claims; "ANSI" is Cyrillic 1251 when most non-ASCII words are entirely Cyrillic, else 1252), CONT / CONC, and GEDCOM dates (ABT / BEF / AFT / BET…AND / FROM…TO, dual years, calendar escapes, phrases) mapped to partial dates; what cannot be read keeps its wording as the date phrase. Names split "Іван Петрович" into first name and patronymic, keep ROMN / FONE variants, married names (`_MARNM`) and nicknames. Places are split into name, region, country and reused when an identical place exists in the tree.

The import runs in two worker steps. First the file is analysed and a preview stored: counts, warnings (unreadable lines, missing family members, photo links that cannot be imported because a `.ged` file holds no files), program-specific tags that are not imported, and people who look like someone already in the tree (same first name and surname in any spelling, compatible gender, birth years at most two apart; "strong" when both years are known). The editor confirms, choosing which of those are the same person. A merged person is kept exactly as is and only receives the family links from the file; we never overwrite existing data from an import.

The second step creates everything through the normal services (revisions, audit, validation), in one database transaction with a savepoint per item: a record the model refuses (a third biological parent, a cycle, an invalid date) is skipped and listed in the result instead of failing the import, while an unexpected error rolls everything back. The services gained a `commit=False` option for this. "Undo import" moves every created person (with their events and relationships) and source to the trash, so it can itself be undone from the trash; created places stay (harmless and possibly reused). Media files referenced by the GEDCOM are not imported. Editors and admins can import. The uploaded file is kept in storage (`imports/<tree>/<id>.ged`).

### D90. Integrity checks re-hash originals; backups belong to the infrastructure

A worker job reads every stored original back and compares size and SHA-256 with the values recorded at upload (soft-deleted media included, since their originals are kept); derived files are not checked because they can be regenerated. It runs every Sunday at 04:23 and on demand from the admin System page ("Check now", one run at a time; a run still "running" after 12 hours is treated as interrupted). Problems are stored per run (`integrity_issues`) and shown with the tree and file name; files under `originals/` that no record points at are counted. Progress is committed page by page so the page can follow it.

Scheduled backups with retention and an off-site copy are left to the hosting infrastructure (database backups of the managed PostgreSQL cluster, snapshots / replication of the media volume): the operator already runs them for every application, and an in-app backup would duplicate that while needing write access to backup storage. The manual `make backup` / `make restore` scripts stay for self-hosters without such infrastructure.

## After phase 9

### D91. A bigger demo family that existing copies grow into

The demo family grew from 25 people in 5 generations to 66 people in 7 (1830s–2010s) so the tree shows what a real archive looks like: two older generations, the parents of everyone who married in (several root couples at different heights: Kovalenko and Boyko at the bottom, Melnyk, Tkach, Shevchuk and Hnatiuk a generation up, Romanenko and Lytvyn later), side branches (a Holodomor victim, a second Canadian branch in Winnipeg, the Tkach line down to 2001) and the youngest generation. The original 25 people are unchanged and stay first in the list, so their portraits (seeded by position) and every test or tour that refers to them still hold.

`make seed` (`complete_demo`) now also adds people that a copy does not have yet, matched by first and last name, with their links, events, places and portraits, and replaces the first version's tree description unless the owner changed it. Names of people in the trash count as present, so someone the owner deleted is not brought back; links and marriages are only added when they involve a newly added person, so nothing the owner rearranged is redone. Cards the owner dragged keep their saved offsets, which can look odd next to the new people until "Reset layout".

### D92. Cards never overlap on the canvas

Saved card offsets are relative to the automatic layout, so when the family grows (new people move the automatic positions) or a card is dropped onto another, cards could end up on top of each other. After offsets are applied, a sweep from left to right pushes any card that overlaps an already placed one (same or neighbouring row) to the right, just far enough, which can push the cards after it; nothing moves vertically and the left-to-right order is kept. Cards that do not overlap keep their exact position, so a tree without overlaps looks the same as before. This only affects drawing: the saved offsets are not changed. While dragging, the dragged cards follow the pointer and the rest stay put; on drop the others make room. Tangled lines from old drags still need "Reset layout".

### D93. Couples get a visible link

Partners stood side by side, but only their shared knot above showed they belonged together, and a couple without children looked like two strangers. A small link now spans the gap between partners' cards (the gap grew from 24 to 56 px to make room): interlocked rings and the wedding year for a marriage, a dashed line with a heart for unmarried partners or a civil union, the rings struck through after a divorce or separation. Widowhood keeps the normal link, since the † on the card already says it. Hovering the badge shows the type, date, place and how it ended. The graph endpoint now also returns each partnership's `end_reason` and place name. The link is drawn only when the partners are next to each other in a row (not when dragged far apart), dims with the line highlighting, and is part of PNG / PDF exports. The demo family gained a divorced couple and unmarried partners (66 people) so all three looks appear.

### D94. "Share" adds existing users only; invitations stay on the Members page

Sharing a tree is the same thing as adding a member, so "Share" (on the tree card and in the builder toolbar, for the tree's admins) uses the existing members endpoint with `invite: false`. Then an email without an account is an error (`404 no_user_with_email`, "No user with this email exists") instead of silently creating an invitation link: sharing should either work at once or say why not. Inviting someone new (a one-time link the admin sends) remains on the Members page, which keeps `invite: true`. The access levels are shown in plain words (can view / suggest changes / edit / manage access) for the existing roles. Adding someone who is already a member answers `409 already_member`.

### D95. Welcome guide and "What's new", remembered per account

At sign-in a new user sees a short welcome guide (six steps: trees, exploring, builder, archive, discovery views, sharing and import) until they tick "Don't show this again"; closing it without ticking brings it back at the next sign-in. Users who already know the app instead see "What's new": the changelog entries newer than the last one they saw, once; ticking "Don't show news when I sign in" stops the popup. Both are always available from the footer. The state lives on the user (`welcome_dismissed`, `changelog_seen`, `show_changelog`, migration 0009, set through `PATCH /auth/me` and not audited), so it follows the person across devices; a browser-session flag keeps either popup from reappearing on every reload. The migration marks the welcome guide as seen for everyone who had already signed in. The changelog is a typed list in the frontend (`features/onboarding/changelog.ts`, en / uk / pl, ids are dates): it ships with the code that it describes, and adding an entry is part of finishing a user-visible change (CLAUDE.md). End-to-end tests close both popups automatically (`e2e/popups.ts`, Playwright locator handlers).

### D96. GEDCOM export mirrors the importer and is tested by a round trip

`app/exporters/gedcom.py` writes GEDCOM 5.5.1 in UTF-8 straight from the tables (people, names, principal events, places, parent links, partnerships, sources, citations; deleted rows left out). It mirrors the importer's mapping so a file goes out and comes back unchanged: given names carry the patronymic ("Іван Петрович"), married names get `TYPE married` and a separate birth-surname `NAME` when only `maiden_name` holds it, adoptive / foster / step links use `PEDI`, divorce `DIV`, separation `_SEPR`, unmarried partners a `FAM` without `MARR`, military service `_MILT`, other types `EVEN` + `TYPE`; event titles go into `TYPE` (the importer now reads them back for every event); cemetery and plot into `ADDR`; coordinates into `PLAC.MAP`; partial dates as `ABT` / `BEF` / `AFT` / `BET…AND`, phrases as `(…)` or `INT … (…)`; long text continues with `CONC` / `CONT`; `@` is escaped. Families are rebuilt from the links: one `FAM` per set of parents, plus couples without children. The test exports the 66-person demo family, imports the file into an empty tree with our own importer and requires the same number of people, parent links and partnerships with no warnings.

Any member who can view the tree can export it (they can already see everything in it); each export is audited (`tree.export`). `living=false` keeps living people in the family structure as "Living <surname>" without dates, notes or sources, for files that will be shared outside the family. Media files are not included: a GEDCOM file holds text only; the family archive ZIP with media remains in phase 11. The file name is the tree name and date (RFC 5987, with a transliterated ASCII fallback).

### D97. Measured performance for large trees; simplified cards when zoomed out

Phase 10's performance test is `make perf`: it starts a throwaway production-build stack, generates a realistic synthetic tree (`python -m app.perf`, deterministic, written directly to the tables because the audited services take minutes for thousands of people), and measures the API and the browser with Playwright. Results and the method are in `docs/performance.md`; at 2,000 people every API call is under 0.3 s, the whole tree is laid out in 0.8 s and drawn in 1.5 s, and it pans at 50 fps.

Two changes came out of it. Below 45 % zoom a card is drawn as a frame with the name only (larger type), since portraits and dates are unreadable there and hundreds of full cards made drawing and panning slow; the hover preview is built only while hovering instead of hidden in every card. During a PNG / PDF export every card is drawn in full regardless of zoom (`FullDetail` context). The GEDCOM exporter precomputes each person's families and link types instead of scanning all families per person, which was quadratic (6.3 s → 0.43 s for 5,000 people).

### D98. Share links: a read-only view of one tree, checked on every request

A tree's admins create links in the Share dialog ("Anyone with the link can view"): an optional name, an expiry (7 / 30 / 365 days or none) and a revoke button; the list shows how often each was opened. The URL carries a random token (`/s/<token>`); only its SHA-256 is stored, and the full link is shown once. Opening it (`POST /share/{token}/open`) puts the token into an httpOnly cookie for `/api` (at most 30 days, never past the link's expiry). Tree access then works like this: without a signed-in user, the cookie gives viewer access to that one tree for GET requests only; a signed-in user who is not a member of the tree also gets that read-only view (so a link from a relative works whether or not you are signed in). The link is looked up on every request, so revoking or expiry takes effect at once, and a deleted tree ends its links. The services see a link visitor as a transient, never-stored "guest" user with the viewer role, so existing read endpoints, media and the whole tree UI work unchanged; everything else (the tree list, profile, admin, editing, GEDCOM export) still needs an account. The frontend asks `/share/session` when nobody is signed in and shows the tree pages with a "Shared view" badge and a "Sign in" link.

Living people are shown to link visitors exactly as to viewers. The dialog says so plainly and recommends an expiry; hiding living people from link visitors is a possible follow-up.

### D99. The user guide lives in the app, written in Markdown next to the code

The full guide is a page at `/help` (footer "User guide", and a link in the welcome guide), open without signing in. It is two Markdown files in the frontend (`features/help/guide.uk.md`, `guide.en.md`) imported as text and rendered with a table of contents from the `##` headings (ids that work for Cyrillic headings too). Keeping it in the repository next to the features means a change and its documentation land together (CLAUDE.md asks for it), and a test checks that both languages have the same sections. Polish users see the English text with a note until a translation exists. `docs/user-guide.md` only points to the files.

### D100. Client IPs come from trusted proxies only

The client IP is used for login throttling (failures per IP) and recorded in the change history. Requests reach the backend through ingress-nginx and the app's nginx, so the real address is in `X-Forwarded-For`; uvicorn used to believe that header from any peer (`--forwarded-allow-ips='*'`) and then took its leftmost entry, which the client writes itself — a script could pick any IP and so dodge the per-IP limit. Now the app wraps itself in uvicorn's `ProxyHeadersMiddleware` with `TRUSTED_PROXIES` (default: loopback and the private networks used by Docker and Kubernetes pods) and uvicorn's own handling is off. Headers are only read when the direct peer is trusted, and the client is the rightmost address that is not a trusted proxy, so anything the client prepends is ignored. A deployment behind a public CDN or load balancer adds its ranges to `TRUSTED_PROXIES`. Doing it in the app rather than on the uvicorn command line makes it testable (`test_client_ip_from_trusted_proxies`).

### D101. Two-step verification secrets are encrypted at rest

A TOTP secret is as good as the second factor itself, so a database dump or backup must not reveal it. Secrets are stored as `enc1:` + a Fernet token (AES-128-CBC + HMAC-SHA256, `cryptography`). The key is `DATA_ENCRYPTION_KEY` when set, otherwise derived from `SECRET_KEY` with HKDF (a separate purpose label, so the token-signing key is never used directly). Decryption tries both keys, so setting `DATA_ENCRYPTION_KEY` later keeps existing secrets readable; new ones are encrypted with it. A secret that cannot be decrypted (keys changed) is an error, never "no 2FA": the login fails and an administrator can reset that user's 2FA. Encryption happens in the auth service, not in a column type, so a key problem affects only 2FA sign-ins instead of every request that loads a user. Migration 0011 widens the column and encrypts existing secrets (the downgrade decrypts them). Values without the prefix are still read as plaintext.

### D102. Route-level code splitting

The frontend shipped as one 1.3 MB script (400 kB gzipped), including React Flow, Leaflet (through the place picker in the editor), the Markdown guide and every admin page, before the sign-in form appeared. Now every page except sign-in, the tree list and "not found" is loaded with `React.lazy` on first visit; the layout and the admin layout show a spinner while a page loads. The first load is 450 kB (143 kB gzipped); the tree canvas (233 kB), Leaflet (149 kB) and the guide come separately. After a deploy, a tab opened earlier may request page files that no longer exist; Vite's `vite:preloadError` event then reloads the page once (guarded per path in sessionStorage). The change exposed a race in opening a share link (a share-session check still waiting for a failed token refresh overwrote the new session); opening a link now cancels that check first.
