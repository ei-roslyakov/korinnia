#!/bin/sh
# Usage: docker-entrypoint.sh {api|api-dev|worker|migrate|<any command>}
# Operator commands: docker compose exec backend python -m app.cli --help
set -eu

case "${1:-api}" in
  api)
    alembic upgrade head
    python -m app.cli bootstrap
    # X-Forwarded-* is handled in the app, from TRUSTED_PROXIES only (app/main.py).
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-proxy-headers
    ;;
  api-dev)
    alembic upgrade head
    python -m app.cli bootstrap
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir app \
      --no-proxy-headers
    ;;
  worker)
    exec python -m app.jobs.worker
    ;;
  migrate)
    exec alembic upgrade head
    ;;
  *)
    exec "$@"
    ;;
esac
