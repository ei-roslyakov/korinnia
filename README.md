# Korinnia (Коріння)

**A self-hosted family archive and interactive family tree.**

Korinnia ("roots" in Ukrainian) collects *everything* about every family member — names in every
spelling, life events, biographies, photos, documents, recordings, stories and sources — in one
place, so that future generations can still read it decades from now. Every design decision
favours data durability, completeness and open formats.

**Try it:** the demo is available at [korinnia.app](https://korinnia.app) → "Try the demo" gives you a throwaway account
with a fictional seven-generation family to explore and edit for 30 minutes.

> Korinnia is built with AI: the code is written by [Claude](https://claude.com/claude-code)
> (Anthropic's Claude Code) under the direction and review of the maintainer.

## Highlights

- **A tree that looks like a tree** — the family grows upwards from a trunk and roots, one row per
  generation, with couples, adoptive and step links, focus mode and smooth zooming through 2,000+
  people. Export it as PNG or PDF.
- **Built for real genealogy** — any number of names per person in any script, partial and
  approximate dates, places with historical names, sources and citations on every fact, full
  revision history and a trash bin.
- **Media archive** — photos (incl. HEIC), scans, PDFs, audio and video; originals kept
  byte-for-byte with SHA-256 checksums and checked weekly; face tagging and portraits.
- **Family together** — per-tree roles (viewer, contributor, editor, admin), suggestions and
  stories with moderation, comments, research questions, share links for people without an
  account.
- **Insights** — relationship calculator with kinship terms in Ukrainian, English and Polish, family
  map, timeline with historical context, "On this day", statistics.
- **Your data stays yours** — GEDCOM 5.5.1 import and export (MyHeritage, Ancestry, Gramps,
  FamilySearch…), self-hosted, plain files on disk, PostgreSQL.
- **Secure by default** — argon2id, optional TOTP two-step verification, httpOnly cookies, CSRF
  protection, login throttling, audit log of every change.
- Interface in **English, Ukrainian and Polish**, with light, dark, sepia and "Night" themes.

The full list is in [docs/features.md](docs/features.md).

## Quick start

You need Docker with Docker Compose v2 and `make`.

```bash
git clone https://github.com/ei-roslyakov/korinnia.git && cd korinnia
make up
```

Open <http://localhost:8080> and sign in as `admin@example.com` / `change-me-now-please`
(from `.env`, which `make up` creates from `.env.example`). Every new account gets its own copy of
the demo family.

- [Development](docs/development.md) — commands, tests, conventions, troubleshooting
- [Self-hosting](docs/self-hosting.md) — production setup, Helm chart, configuration, backups

## Tech stack

FastAPI · PostgreSQL 16 (data *and* job queue) · SQLAlchemy 2 · React 19 · TypeScript · Vite ·
Tailwind CSS · React Flow + ELK · Leaflet / OpenStreetMap · nginx · Docker Compose / Helm.
See [docs/architecture.md](docs/architecture.md).

## Roadmap

- **"You are in a family tree"** — link a person to a user account; that user sees where they
  appear and can request access
- **Family archive export** — a ZIP with an offline static website, JSON + GEDCOM, Markdown and
  the original media with a manifest
- **Printable PDF family book**
- Optional email sign-up and "Sign in with Google"
- AI-assisted import from social media exports, reviewed by an editor before anything is saved
- Later: letters to descendants (sealed until a date), duplicate detection and merge, PWA

## How it's built

Korinnia is developed together with Claude, an AI model by Anthropic, using Claude Code. The
maintainer decides what to build, describes features, tests every change and reviews it before
it ships; Claude writes most of the code, tests and documentation. Commits made this way carry a
`Co-Authored-By: Claude` trailer. Working notes for these sessions live in [CLAUDE.md](CLAUDE.md)
and [plans/](plans/README.md), and the reasoning behind design choices in
[docs/decisions.md](docs/decisions.md).

## Documentation

- [Features](docs/features.md)
- [Architecture](docs/architecture.md) and [design decisions](docs/decisions.md)
- [Data schema](docs/data-schema.md)
- [Development](docs/development.md) and [self-hosting](docs/self-hosting.md)
- [Backup and restore](docs/backup-restore.md), [performance on large trees](docs/performance.md)
- [User guide](docs/user-guide.md) (in the app at `/help`)
- [Contributing](CONTRIBUTING.md) and [security policy](SECURITY.md)

## License

Copyright © 2026 Yevhenii Rosliakov. Korinnia is free software under the
[GNU Affero General Public License v3.0](LICENSE): you may use, self-host, modify and share it.
If you run a modified version for other people over a network, you must offer them its source
code under the same licence. Family content added to an installation belongs to its authors and
is not covered by this licence.

Korinnia uses open-source components under their own licences; their notices are in
[frontend/public/third-party-notices.txt](frontend/public/third-party-notices.txt), also served by
the app at `/third-party-notices.txt`.
