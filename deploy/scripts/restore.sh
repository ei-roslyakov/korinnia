#!/usr/bin/env bash
# Restore a backup produced by backup.sh. DESTRUCTIVE: replaces the current database
# contents and media files.
#
# Usage: deploy/scripts/restore.sh backups/<timestamp> [--yes]
set -euo pipefail

cd "$(dirname "$0")/../.."
COMPOSE=${COMPOSE:-docker compose}
PROJECT=${PROJECT:-korinnia}
src=${1:?usage: restore.sh <backup-dir> [--yes]}
src_abs=$(cd "${src}" && pwd)

for f in db.dump media.tar SHA256SUMS; do
  [[ -f "${src}/${f}" ]] || { echo "missing ${src}/${f}" >&2; exit 1; }
done

echo ">> verifying checksums"
(cd "${src}" && (sha256sum -c SHA256SUMS 2>/dev/null || shasum -a 256 -c SHA256SUMS))

if [[ "${2:-}" != "--yes" ]]; then
  read -r -p "This REPLACES the current database and media with ${src}. Type 'restore' to continue: " answer
  [[ "${answer}" == "restore" ]] || { echo "aborted"; exit 1; }
fi

echo ">> stopping application services"
$COMPOSE stop backend worker nginx
$COMPOSE up -d --wait postgres

echo ">> restoring database"
$COMPOSE exec -T postgres sh -c \
  'dropdb -U "$POSTGRES_USER" --if-exists --force "$POSTGRES_DB" && createdb -U "$POSTGRES_USER" "$POSTGRES_DB"'
$COMPOSE exec -T postgres sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --exit-on-error' \
  < "${src}/db.dump"

echo ">> restoring media volume"
docker volume create "${PROJECT}_media" >/dev/null
docker run --rm -v "${PROJECT}_media:/data/media" -v "${src_abs}:/backup:ro" alpine:3 \
  sh -c 'find /data/media -mindepth 1 -delete && tar -C /data -xpf /backup/media.tar'

echo ">> starting application services"
$COMPOSE up -d --wait backend worker nginx
echo ">> restore complete"
