# Self-hosting

## Docker Compose

`make up-prod` (or `docker compose -f docker-compose.yml up -d --build`) runs the stack without the
development overrides: the frontend is built into the nginx image and the API docs are off.

Before using it for a real archive, set in `.env`:

- `ENVIRONMENT=production`
- a strong `SECRET_KEY` (`openssl rand -hex 32`) and `POSTGRES_PASSWORD`
- `PUBLIC_BASE_URL`, `COOKIE_SECURE=true`, `HTTP_PORT`
- a superadmin email and password
- `DEMO_TREE_FOR_NEW_USERS=false` if new members should not get the demo family

Put nginx behind a TLS-terminating ingress or load balancer that forwards `X-Forwarded-Proto` and
sends HSTS.

## Kubernetes

Each [release](https://github.com/ei-roslyakov/korinnia/releases) publishes public images and a
Helm chart to GitHub Container Registry:

- `ghcr.io/ei-roslyakov/korinnia/backend:X.Y.Z` (API and worker)
- `ghcr.io/ei-roslyakov/korinnia/nginx:X.Y.Z` (frontend and media)
- `oci://ghcr.io/ei-roslyakov/charts/korinnia --version X.Y.Z`

Images are also tagged `X.Y` and `latest`.

```bash
helm install korinnia oci://ghcr.io/ei-roslyakov/charts/korinnia --version X.Y.Z -f my-values.yaml
```

The chart uses the images of its own version by default. Every setting is documented in
[`values.yaml`](../deploy/helm/korinnia/values.yaml). It expects an external PostgreSQL 16 (e.g. a
CloudNativePG cluster) and a ReadWriteMany volume for media. To build the images yourself, use
`backend/Dockerfile` and `deploy/nginx/Dockerfile` with target `prod`.

## Configuration

All settings are environment variables; the full list with comments is in
[`.env.example`](../.env.example). The most important ones:

| Variable | Purpose |
|---|---|
| `ENVIRONMENT` | `development` or `production`. Production disables the API docs |
| `SECRET_KEY` | Signs auth tokens. Generate with `openssl rand -hex 32` |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | Database credentials |
| `SUPERADMIN_EMAIL` / `SUPERADMIN_PASSWORD` | First administrator, created on first start if no superadmin exists (min. 10 characters). Changing them later has no effect |
| `PUBLIC_BASE_URL` | Public URL of the app, used to build invitation and password-reset links |
| `COOKIE_SECURE` | `true` (default) marks auth cookies HTTPS-only. Set `false` only for plain-HTTP local development |
| `MAX_UPLOAD_SIZE_MB` | Maximum size of one upload; also sets nginx `client_max_body_size` |
| `DEFAULT_LANGUAGE` | Interface language for visitors and new accounts: `en` (default), `uk` or `pl` |
| `DEMO_TREE_FOR_NEW_USERS` | Give each new account its own copy of the demo family (default `true`) |
| `USERS_CAN_CREATE_TREES` | Let every user start their own trees (default `true`) |
| `SESSION_TIMEOUT_MINUTES` | Sign users out after this long (default 480) |
| `DEMO_LOGIN_ENABLED` | Public demo mode: throwaway accounts with a fresh demo family (default `false`) |
| `TRUSTED_PROXIES` | Networks whose `X-Forwarded-For` is believed (default: private networks) |
| `WORKER_CONCURRENCY` | Number of jobs the worker runs in parallel |
| `HTTP_PORT` | Host port for nginx |

## Operator commands (lock-out recovery)

Korinnia does not send email: administrators copy invitation and password-reset links from the UI
and pass them on. If the only administrator is locked out, use the CLI inside the backend container:

```bash
docker compose exec backend python -m app.cli reset-link admin@example.com     # one-time reset link
docker compose exec backend python -m app.cli disable-2fa admin@example.com    # lost authenticator
docker compose exec backend python -m app.cli create-superadmin you@example.com "Your Name"
```

## Backups

`make backup` writes `backups/<UTC timestamp>/` with a `pg_dump` of the database, a `tar` of the
media volume and a `SHA256SUMS` file; `make restore dir=backups/<timestamp>` verifies the checksums
and replaces the database and media. Scheduled backups, retention and off-site copies are the job
of your hosting infrastructure. Details: [backup-restore.md](backup-restore.md).
