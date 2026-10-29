# Performance

Measured with `make perf` (`PEOPLE=2000` by default): a throwaway production-build stack, a
synthetic tree from `python -m app.perf` (founding couples around 1800, 2–5 children per couple,
most children marrying in from other families, about nine generations, births, deaths and
places), API timings from the browser through nginx (median of three) and browser timings with
Playwright / Chromium (1440×900). Run on a developer laptop (Docker Desktop), 2026-10-11.

| | 2,000 people | 5,000 people |
|---|---|---|
| Generate the tree (`app.perf`) | 1.2 s | 3.1 s |
| API: whole graph (`/graph`, 260 KB gzipped at 2,000) | 151 ms | 461 ms |
| API: person page | 28 ms | 74 ms |
| API: search | 29 ms | 90 ms |
| API: statistics | 270 ms | 740 ms |
| API: timeline / map | 155 ms | 460 ms |
| API: relationship calculator | 24 ms | 100 ms |
| API: chart lineage, 8 generations of ancestors / descendants (2026-10-29) | 23 / 30 ms | — |
| API: GEDCOM export | 0.17 s | 0.43 s |
| GEDCOM import (worker): analysis + import | 1.4 s + 19 s | — |
| Open the tree (focus mode, first card) | 0.8 s | 0.8 s |
| Switch to the whole tree: layout (ELK in a worker) | 0.8 s | 2.0 s |
| Whole tree drawn and settled | 1.5 s | 2.9 s |
| Panning the whole tree | 50 fps | 35 fps |
| Longest main-thread task | 284 ms | 471 ms |
| JS heap | 111 MB | 45 MB |

Changes made because of these measurements (D97):

- Cards are drawn simply (name only) when zoomed out far, and the hover preview is only
  built while hovering (the threshold was 45 % at first; since 2026-10-15 it is 15 %, so
  trees of a few dozen people open with portraits and years, D107): the whole 2,000-person tree went from 2.4 s to 1.5 s, the longest task
  from 764 ms to 284 ms, panning from 44 to 50 fps, memory from 179 MB to 111 MB.
- GEDCOM export no longer scans every family for every person: 1.1 s → 0.17 s at 2,000 people,
  6.3 s → 0.43 s at 5,000.

The chart views' lineage endpoint (D118) loads the tree's links once (like the relationship
calculator) and walks them in memory, so 8 generations cost about the same as 4: 23 ms for the
youngest person's ancestors and 30 ms for a founder's descendants at 2,000 people (target:
under 300 ms). Measured 2026-10-29; the other rows of that run matched the table within a few
milliseconds.

Trees above 150 people open in focus mode (D43), so the first view stays fast whatever the size.
`make perf-tree people=N` adds such a tree to the dev stack to try it by hand.
