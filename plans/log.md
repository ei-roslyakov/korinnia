# Work log

Newest first. One entry per finished task: what changed, why, commit, anything left open.

## 2026-10-08

- **"Import GEDCOM" next to "New tree"** (superadmins, like "New tree"): creates a tree named
  after the file and opens the preview; cancelling removes that tree; a refused file deletes it
  at once. Empty trees also offer "or import a GEDCOM file". (commit "Phase 9: GEDCOM import and integrity checks")
- **Phase 9 (parts 1–2): GEDCOM import and integrity checks** — backups are left to the
  infrastructure (owner's decision). D89, D90; migration 0008 (`gedcom_imports`,
  `integrity_runs`, `integrity_issues`).
  - GEDCOM: own reader (`app/importers/gedcom/`: encodings incl. ANSEL / cp1251, dates, names
    with patronymics), service `services/gedcom_import.py` (analyse → preview with duplicate
    candidates → confirm with merges → import in one transaction, savepoint per item → undo
    via trash), API `/trees/{id}/imports`, page `/trees/:id/import` ("Import GEDCOM" in the
    builder toolbar). Create services got `commit=False` (events, places, sources, citations).
  - Integrity: weekly worker job (Sun 04:23) + "Check now" on Admin → System status; issues
    listed with tree and file.
  - Tests: backend 306 passed (new: parser, import API, integrity), frontend 136, E2E 23
    (local). Verified in the dev app with a sample file. (commit "Phase 9: GEDCOM import and integrity checks")
- **Fix: tree download box moved to the top-right** — at the top-left it covered the spot where
  the E2E test (and users) start dragging the canvas; it was the last CI E2E failure. (75b8f97)
- **CI end-to-end tests fixed (config)** — CI E2E had failed since English became the default
  (7b3134f): the CI stack started without `DEFAULT_LANGUAGE=uk` / `DEMO_TREE_FOR_NEW_USERS=false`,
  which `make test-e2e` sets, so tests could not find the Ukrainian labels. Added both to the CI
  `.env`. (commit "Phase 9: GEDCOM import and integrity checks")
- **Tree export to PNG / PDF** — "Download: PNG | PDF" in the top-left corner of the tree canvas
  (view and builder). Whole tree with title, people count and date; current theme and style. New
  dependency `html-to-image` 1.11.11 (notices regenerated); own one-page PDF writer `lib/pdf.ts`.
  D88. Verified by downloading both from the local app (PNG 6858×3276, PDF on A2). (d8267da)
- **Added `plans/`** (this folder: README, roadmap, implementation overview, log) and `CLAUDE.md`
  telling every session to read and update it.

## 2026-10-07

- **Person delete in builder side panel** — red "Delete" next to Focus here / Open full page /
  Edit, opens the existing move-to-trash preview; only in Builder mode. (737cf47, v0.0.8)
- **Rename and delete trees from the list and the builder toolbar** — shared `TreeActions`
  component; deleting the open tree returns to the list. (737cf47)
- **Delete a tree from its card on the tree list.** (bdde67b, v0.0.7)
- **Tree deletion by tree admins; admin "Trees" tab** — list all trees (incl. deleted), delete,
  restore (`POST /admin/trees/{id}/restore`); demo copy restore refused when a newer one exists.
  D86. (b5c6ba7)
- **Production fix: media volume not writable** — `/api/readyz` returned 503 "storage root not
  writable"; csi-driver-nfs resets the volume root to 0755 on each mount and nginx has no fsGroup.
  Init container in backend/worker/nginx sets group 1000, mode 2775. Verified in prod: readyz 200.
  D87. (2c2dd89, v0.0.6)
- **Licence, footer, third-party notices, app version** — re-added after the revert, without the
  security-scan changes; version passed from the Deploy workflow into both images. D85. (b603610)
- **Revert of licence + security-scan changes** — the app stopped loading locally; reverted
  without touching CI / Argo commits. (93c568f)
- Earlier the same day: phases 1–8, tree layout and styles, themes, demo family, Helm/Argo deploy —
  see `git log` and `implementation.md`.

### Open after 2026-10-07

- Phase 9 waits for the go-ahead.
- Vite dev cache fix (see roadmap "Open issues") waits for the owner's OK.
