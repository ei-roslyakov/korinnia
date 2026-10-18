# Contributing

Thanks for your interest in Korinnia! It is a small project maintained by one person, so:

- **Open an issue first** for anything larger than a small fix, so we can agree on the approach
  before you spend time on it.
- Bug reports are welcome: what you did, what you expected, what happened, browser and version
  (shown in the footer).
- Security problems: see [SECURITY.md](SECURITY.md) — do not open a public issue.

## Development

Everything runs in Docker; see [docs/development.md](docs/development.md) for setup, commands and
conventions. In short: `make up`, then <http://localhost:8080>.

Before opening a pull request:

- `make lint` and `make test` pass (`make test-e2e` for changes to UI flows).
- UI strings go into all three locale files (`frontend/src/i18n/locales/{en,uk,pl}.json`); if you
  don't speak Ukrainian or Polish, add English text there and say so in the PR.
- Changes users will notice get a "What's new" entry in
  `frontend/src/features/onboarding/changelog.ts`; changes to how the app is used also update the
  user guide (`frontend/src/features/help/guide.{en,uk}.md`).
- Schema changes need an Alembic migration and an update to [docs/data-schema.md](docs/data-schema.md).
- Keep pull requests focused: one change per PR.

## Licence of contributions

Korinnia is licensed under the [AGPL-3.0](LICENSE). By submitting a pull request you agree that
your contribution is licensed under the AGPL-3.0 and that the maintainer may also distribute it
under other terms. The checkbox in the pull request template confirms this.
