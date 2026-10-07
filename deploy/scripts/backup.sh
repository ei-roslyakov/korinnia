#!/usr/bin/env bash
# Back up the PostgreSQL database and the media volume.
#
# Output: backups/<UTC timestamp>/
#   db.dump        pg_dump custom format (restore with pg_restore)
#   media.tar      all original + derived media files (plain tar, readable anywhere)
#   SHA256SUMS     checksums of the two files above
#
# Usage: deploy/scripts/backup.sh [output-root]       (default: ./backups)
# Env:   COMPOSE (default "docker compose"), PROJECT (default "korinnia")
#
# Scheduling, retention and off-site copies are added in phase 9 (see docs/backup-restore.md).
set -euo pipefail

cd "$(dirname "$0")/../.."
COMPOSE=${COMPOSE:-docker compose}
PROJECT=${PROJECT:-korinnia}
root=${1:-backups}
stamp=$(date -u +%Y%m%dT%H%M%SZ)
dest="${root}/${stamp}"
mkdir -p "${dest}"
dest_abs=$(cd "${dest}" && pwd)

echo ">> dumping database"
$COMPOSE exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc --no-owner' \
  > "${dest}/db.dump"

echo ">> archiving media volume"
docker run --rm -v "${PROJECT}_media:/data/media:ro" -v "${dest_abs}:/backup" alpine:3 \
  tar -C /data -cf /backup/media.tar media

(cd "${dest}" && sha256sum db.dump media.tar > SHA256SUMS 2>/dev/null \
  || shasum -a 256 db.dump media.tar > SHA256SUMS)

echo ">> backup written to ${dest}"
cat "${dest}/SHA256SUMS"
