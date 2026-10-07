# Backup & restore

Your family archive lives in two places, and **both** must be backed up:

1. **PostgreSQL**: all structured data (people, names, events, relationships, stories, sources, history).
2. **Media volume** (`/data/media`, Docker volume `korinnia_media` or a Kubernetes PVC): original photos, scans, documents, audio and video, plus derived thumbnails.

## Current state (phase 1): manual backups

### Create a backup

```bash
make backup                 # or: deploy/scripts/backup.sh [output-root]
```

This creates `backups/<UTC timestamp>/` with:

| File | Content | How to read it without Korinnia |
|---|---|---|
| `db.dump` | `pg_dump -Fc` of the database | `pg_restore -f db.sql db.dump` produces plain SQL |
| `media.tar` | Every file in the media volume | `tar -xf media.tar`, standard on every OS |
| `SHA256SUMS` | Checksums of both files | `sha256sum -c SHA256SUMS` |

**Copy the backup folder to another disk and another location.** A backup on the same machine is not a backup.

### Restore

```bash
make restore dir=backups/20261007T055549Z      # asks for confirmation
deploy/scripts/restore.sh backups/<timestamp> --yes   # non-interactive
```

The script:
1. verifies `SHA256SUMS` and aborts on any mismatch,
2. stops backend, worker and nginx,
3. drops and recreates the database, then runs `pg_restore`,
4. empties the media volume and extracts `media.tar`,
5. starts the services again. The backend applies any newer migrations on start.

### Restore on a clean machine

1. Install Docker and clone the repository (the same or a newer version).
2. `cp .env.example .env` and set the same `POSTGRES_*` values as before (or new ones; the dump is restored without owners).
3. `make up` and wait until it reports healthy.
4. Copy the backup folder to the machine and run `make restore dir=<folder>`.

**Tested:** a backup → delete data → restore round-trip (database rows with Cyrillic text, media files and the job-queue schema) was verified in phase 1.

## Planned (phase 9)

- Scheduled backups run by the worker, with a retention policy (e.g. 7 daily, 4 weekly, 12 monthly).
- A second copy to another local volume and to a remote S3-compatible bucket (3-2-1 rule).
- Periodic integrity checks that re-hash stored originals against the SHA-256 recorded at upload.
- Automated restore test in CI.
