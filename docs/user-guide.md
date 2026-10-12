# User guide

The user guide is part of the app: open **User guide** in the footer of any page, or go to
`/help`. It is shown in Ukrainian or English (Polish users get the English text for now).

The texts live next to the code they describe, so they change together:

- English: [`frontend/src/features/help/guide.en.md`](../frontend/src/features/help/guide.en.md)
- Українська: [`frontend/src/features/help/guide.uk.md`](../frontend/src/features/help/guide.uk.md)

Both have the same sections (a test checks it). When a change alters how the app is used,
update both guides in the same change, and add a "What's new" entry
(`frontend/src/features/onboarding/changelog.ts`).
