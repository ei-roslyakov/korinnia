# Features

Everything below works today. Planned work is listed in the [roadmap](../README.md#roadmap).

## Family data

- People with any number of names (birth, married, nickname, alias, religious…), each in Cyrillic, Latin or another script, with patronymic and maiden name
- Life events (16 types) with several participants, partial / approximate dates (exact, month, year, about, before, after, between) and places
- Burial details: cemetery, plot, GPS coordinates
- Places with historical names (e.g. Stanislau → Stanisławów → Stanyslaviv → Ivano-Frankivsk) and coordinates
- Parent–child links (biological, adoptive, step, foster, unknown) and partnerships (marriage, civil union, partnership) with start / end and end reason
- Validation: no cycles, no self-relations, at most two biological parents; warnings for implausible dates (child born before parent, parent younger than 12, death before birth, events outside a lifetime, …)
- Relatives computed per person: parents, children, partners, full and half siblings
- Search by any name variant with Ukrainian ↔ Latin transliteration (KMU 2010), maiden names, places (incl. historical names) or birth / death year
- Full revision history of every change (complete snapshots) and restore of any earlier version
- Soft delete with impact preview; trash bin with restore (a person comes back together with their relationships and events)
- Living-person flag inferred when not set (privacy-first default)
- Demo family for every user: an editable copy of a fictional family (66 people, 7 generations from the 1830s to the 2010s, with biographies and illustrated portraits), marked "Demo" and deletable (`DEMO_TREE_FOR_NEW_USERS`)

## Tree view

- Infinite canvas: drag to pan, wheel / pinch to zoom, fit to screen, minimap
- Drawn as a real tree growing upwards: the oldest generation stands on the ground with a trunk and roots, one row per generation above it, partners side by side, curved branches that thin out towards the youngest generations; adoptive / step / foster links dashed; layout (ELK) runs in a Web Worker
- Three tree styles: Simple, Oak (a broad trunk and a leafy crown) and Spring (leaves at every family knot, blossoms on the youngest branches)
- Person cards: portrait, primary name, life years with uncertainty markers (~1850, <1944) and † for the deceased; card text scales smoothly with zoom
- Couples joined by a link: interlocked rings and the wedding year for a marriage, a dashed line with a heart for unmarried partners, struck-through rings after a divorce
- Hover or select a person to highlight their line (ancestors, descendants, partners); generation labels beside each row
- Side panel and full person page with a shareable link: names, birth / death / burial (with map link), facts, Markdown biography, life timeline, relatives, notes for descendants, gallery, documents, sources, stories, research questions and comments
- Focus mode: 1–6 generations around a person, with markers for hidden ancestors / descendants; large trees (>150 people) open in focus mode
- Smooth with 2,000+ people (viewport culling, layout in a worker, simplified cards when zoomed out) — see [performance.md](performance.md)
- Works on tablets and phones (touch pan / zoom, full-width panel)
- Download the tree as an image (PNG) or a one-page PDF: the whole tree, with its name and date, in the current theme and style

## Insights

- Relationship calculator: "how is B related to A?" with the kinship term in Ukrainian (двоюрідний, троюрідний…; тесть / свекор…), English (first cousin once removed…) or Polish, half / adoptive notes, closest common ancestors and the path through the tree
- Family map (OpenStreetMap): places of birth, life, marriage, migration, death and burial; filters by event type and person, with a person's life path drawn in order
- Family timeline: every dated event in chronological order, grouped by decade, with optional historical context (World Wars, Holodomor, Chornobyl, independence…)
- "On this day": birthdays, wedding anniversaries and memorial days for a date or the coming week / month / three months
- Calendar feed: each member can subscribe Google / Apple / Outlook calendars to the tree's birthdays, memorial days and wedding anniversaries (private iCalendar URL, yearly events, language of choice, revocable, follows the member's access and the living-people privacy setting)
- Statistics: people, generations, period covered, oldest ancestor, longest life, average lifespan, surnames (spellings in different scripts grouped), first names, births and deaths by decade

## Builder mode (editors and admins)

- "+" buttons on every card: add a parent, child (with the other parent), partner or sibling — created and linked atomically
- Full person editor: all names, gender, living, research status, birth / death with partial dates and places, occupation, education, religion, nationality
- Markdown editor with live preview for biographies and notes; drafts autosaved in the browser
- Life events editor with participants, roles, burial details and a GPS pin
- Place autocomplete (current and historical names, any script) and "create place" with a map pin
- Family editor: change link types, unlink, link existing people, edit partnership dates and end reason
- Drag cards to adjust the layout: a card moves with its whole branch (hold Alt for a single card); saved per tree, cards never overlap, reset at any time
- Delete with impact preview, trash bin, person history with "restore this version"
- Unsaved-changes warning; validation errors and date warnings shown in place

## Media

- Drag & drop upload with progress: photos (incl. iPhone HEIC), document scans, PDFs, audio, video, text documents; large files streamed
- Originals stored byte-for-byte with SHA-256; type detected from content (HTML / SVG / executables rejected); duplicates detected per tree
- Background processing: EXIF-rotated web versions and thumbnails, video posters + MP4, MP3 for non-browser audio, PDF thumbnails; status, failure reasons, retry
- Gallery with lightbox (keyboard navigation, captions, date, place, people), documents list, audio and video players
- Face / person tagging in group photos; names shown on the photo and linked
- Portraits: pick a photo and crop a square (original untouched)
- A new photo asks for its description (title, date, place optional) and who else is in it (relatives offered in a dropdown, anyone else by name) as soon as it is added in the person editor
- Family album: every processed photo of the tree in a carousel with the description above each photo (title, description with "more", date · place) and the people below; swipe (Embla), arrows on the photo, ←/→, thumbnails, optional slideshow (pauses on hover / focus / hidden tab, off with reduced motion); neighbouring photos preload only, more pages load near the end (D113)
- "Family album" button in the tree header (with the photo count) opens the album in a popup over the tree (Esc / ✕ / click outside closes it); a person chip offers only their photos, show on the tree, or their page; album page `/trees/:id/album` with a large carousel or grid, filters by people and decade, search in descriptions, order by photo date (undated last) or newest upload
- Lightbox: description above the image, swipe between items
- Files served only to tree members (the API checks access, nginx streams the file via `X-Accel-Redirect`, range requests for video)

## Sources, stories and collaboration

- Source library per tree (civil and church records, archive documents, census, newspapers, letters, oral history, books…) with archive, reference number and URL
- Citations on any fact — a person field, a name, an event, a parent link, a partnership or a media item — with page and quality (primary, secondary, family tradition, unverified)
- Stories and memories in Markdown with narrator, date and several people; draft → on review → published
- Edit suggestions from contributors with a before / after diff; editors approve or reject with a comment; moderation page with a pending badge
- Comments on people, stories, photos and videos; open research questions per person
- Data-quality panel: people without a birth record, photo or source, with date problems, or with open questions

## Import, export and data safety

- GEDCOM 5.5 / 5.5.1 import (MyHeritage, Ancestry, Gramps, FamilySearch, Geni…): UTF-8, UTF-16, ANSEL and Windows code pages; preview, probable duplicates to merge instead of creating, everything in one transaction with skipped items explained, "undo import"
- GEDCOM 5.5.1 export with all names, events, places, families, sources and citations; optionally without the details of living people
- Weekly integrity check of stored originals (re-hashed with SHA-256) and on demand; problems listed on the admin System page
- Manual backup / restore of database and media (`make backup` / `make restore`, see [backup-restore.md](backup-restore.md))

## Users, access and security

- Email + password sign-in (argon2id); no public self-registration
- Optional TOTP two-step verification with one-time recovery codes; secrets encrypted at rest
- Short-lived access + rotating refresh JWTs in httpOnly cookies, refresh-token reuse detection, "sign out everywhere" on password change; session timeout with in-place re-sign-in
- CSRF protection (double-submit cookie + SameSite), login throttling per email and per IP, security headers (CSP, nosniff, frame-deny, referrer and permissions policy), client IPs only from trusted proxies
- Multiple trees with per-tree roles: viewer, contributor, editor, admin (enforced on every endpoint)
- Every user can start their own trees (can be turned off per user or site-wide)
- Share a tree with another user by email, invite by one-time expiring link, or create read-only share links for people without an account (expiry, open count, revoke)
- Privacy of living people: share-link visitors (by default), optionally also viewers, see only a living person's name, gender, birth year and family links; enforced by the server on every endpoint (photos, documents, events, stories, comments, map, timeline, album, exports); portraits optional
- Admin panel: users, superadmin rights, password-reset links, 2FA reset, all trees (delete / restore), audit log of every change (who, when, before / after)
- Operator CLI for lock-out recovery
- Optional public demo mode: every visitor gets a throwaway account with a fresh demo family (`DEMO_LOGIN_ENABLED`)

## Interface

- English, Ukrainian and Polish; each user's choice is remembered
- Themes: light, dark, archive (sepia) and Night (frosted glass), or follow the device
- In-app user guide (`/help`, Ukrainian and English), welcome guide for new users and "What's new" at sign-in
- Self-hosted Lora and Inter fonts (with Cyrillic)
