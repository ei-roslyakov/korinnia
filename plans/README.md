# Plans

Working notes so that any new session (human or AI) can pick up where the last one stopped.

| File | What it holds | When to update |
|---|---|---|
| [roadmap.md](roadmap.md) | Where the project stands: finished phases, what is live, what comes next (phases 9–11, backlog), open issues | When a phase or feature starts or finishes, or the plan changes |
| [implementation.md](implementation.md) | How everything that exists was built: architecture, per-phase summary, where the code lives, conventions and gotchas | When something structural changes (new module, new subsystem, new convention) |

Other documents stay where they are and are not repeated here:

- `README.md` — public overview, quick start, roadmap of planned features
- `docs/features.md` — full list of what works; `docs/development.md`, `docs/self-hosting.md`, `docs/architecture.md`
- `docs/decisions.md` — numbered design decisions (D1…); the reasoning behind choices
- `docs/data-schema.md` — tables and columns
- `docs/backup-restore.md`, `docs/user-guide.md`

## Rules for every session

1. Read `roadmap.md` and the recent `git log` before starting work.
2. Write a commit message that says what changed and why; the git history is the work log.
3. If the task changes the plan (a feature done, a new idea, a known problem), update `roadmap.md` in the same change.
4. Keep entries short and factual; link to decisions (`D86`) instead of repeating them.
