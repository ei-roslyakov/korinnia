"""Relationship calculator: how is person B related to person A?

The answer is structural (generations up to the closest common ancestor and down again,
half / non-biological flags, the in-law side, the path). Turning it into a word such as
"троюрідна сестра" or "first cousin once removed" is language-specific and done in the UI.

Order of preference: same person → partners → blood relatives → in-laws (one marriage
step at either end) → any other chain of parent / child / partner links.
"""

from __future__ import annotations

import uuid
from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass, field
from itertools import pairwise
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ParentChildType
from app.core.errors import NotFoundError
from app.models import ParentChild, Partnership, Person
from app.schemas.insights import Edge, KinshipKind, PathStep, Relationship
from app.services.genealogy.summaries import summary_map

# Safety net for pathological data (cycles are rejected on write, but be defensive).
MAX_DEPTH = 200


@dataclass(slots=True)
class FamilyIndex:
    parents: dict[uuid.UUID, list[tuple[uuid.UUID, ParentChildType]]] = field(default_factory=dict)
    children: dict[uuid.UUID, list[uuid.UUID]] = field(default_factory=dict)
    partners: dict[uuid.UUID, list[uuid.UUID]] = field(default_factory=dict)

    def parent_ids(self, pid: uuid.UUID) -> list[uuid.UUID]:
        return [p for p, _ in self.parents.get(pid, [])]

    def link_type(self, parent: uuid.UUID, child: uuid.UUID) -> ParentChildType:
        return next(t for p, t in self.parents.get(child, []) if p == parent)


async def load_index(session: AsyncSession, tree_id: uuid.UUID) -> FamilyIndex:
    live = set(
        await session.scalars(
            select(Person.id).where(Person.tree_id == tree_id, Person.deleted_at.is_(None))
        )
    )
    idx = FamilyIndex()
    for link in await session.scalars(
        select(ParentChild).where(ParentChild.tree_id == tree_id, ParentChild.deleted_at.is_(None))
    ):
        if link.parent_id in live and link.child_id in live:
            idx.parents.setdefault(link.child_id, []).append((link.parent_id, link.type))
            idx.children.setdefault(link.parent_id, []).append(link.child_id)
    for p in await session.scalars(
        select(Partnership).where(Partnership.tree_id == tree_id, Partnership.deleted_at.is_(None))
    ):
        if p.person_a_id in live and p.person_b_id in live:
            idx.partners.setdefault(p.person_a_id, []).append(p.person_b_id)
            idx.partners.setdefault(p.person_b_id, []).append(p.person_a_id)
    return idx


@dataclass(slots=True)
class Blood:
    up: int
    down: int
    common: list[uuid.UUID]
    path: list[uuid.UUID]  # a … ancestor … b
    half: bool
    non_biological: bool


def _ancestors(idx: FamilyIndex, start: uuid.UUID) -> dict[uuid.UUID, tuple[int, uuid.UUID | None]]:
    """Every ancestor (and `start` itself) → (generations up, the child we reached it from)."""
    seen: dict[uuid.UUID, tuple[int, uuid.UUID | None]] = {start: (0, None)}
    queue = deque([start])
    while queue:
        node = queue.popleft()
        depth = seen[node][0]
        if depth >= MAX_DEPTH:
            continue
        for parent in idx.parent_ids(node):
            if parent not in seen:
                seen[parent] = (depth + 1, node)
                queue.append(parent)
    return seen


def _line(anc: dict[uuid.UUID, tuple[int, uuid.UUID | None]], top: uuid.UUID) -> list[uuid.UUID]:
    """From the start person up to `top`."""
    out = [top]
    node: uuid.UUID | None = anc[top][1]
    while node is not None:
        out.append(node)
        node = anc[node][1]
    return list(reversed(out))


def blood(idx: FamilyIndex, a: uuid.UUID, b: uuid.UUID) -> Blood | None:
    if a == b:
        return Blood(0, 0, [a], [a], False, False)
    anc_a, anc_b = _ancestors(idx, a), _ancestors(idx, b)
    common = anc_a.keys() & anc_b.keys()
    if not common:
        return None
    # Closest common ancestor(s): fewest steps in total; prefer the shorter way up.
    best = min(common, key=lambda c: (anc_a[c][0] + anc_b[c][0], anc_a[c][0], str(c)))
    up, down = anc_a[best][0], anc_b[best][0]
    tied = sorted(
        (c for c in common if anc_a[c][0] == up and anc_b[c][0] == down), key=lambda c: str(c)
    )
    line_a, line_b = _line(anc_a, best), _line(anc_b, best)
    path = line_a + list(reversed(line_b))[1:]

    half = False
    if up >= 1 and down >= 1:
        # The two children of the common ancestor(s) on each line: half-siblings share
        # exactly one parent while both have two known parents.
        branch_a, branch_b = line_a[-2], line_b[-2]
        pa, pb = set(idx.parent_ids(branch_a)), set(idx.parent_ids(branch_b))
        half = len(pa) == 2 and len(pb) == 2 and len(pa & pb) == 1

    def non_bio(line: list[uuid.UUID]) -> bool:
        return any(
            idx.link_type(parent, child) != ParentChildType.biological
            for child, parent in pairwise(line)
        )

    return Blood(up, down, tied, path, half, non_bio(line_a) or non_bio(line_b))


def _shortest_path(idx: FamilyIndex, a: uuid.UUID, b: uuid.UUID) -> list[uuid.UUID] | None:
    """Any chain of parent / child / partner links (breadth-first)."""
    prev: dict[uuid.UUID, uuid.UUID | None] = {a: None}
    queue = deque([a])
    while queue:
        node = queue.popleft()
        if node == b:
            out: list[uuid.UUID] = []
            cur: uuid.UUID | None = b
            while cur is not None:
                out.append(cur)
                cur = prev[cur]
            return list(reversed(out))
        for nxt in (
            *idx.parent_ids(node),
            *idx.children.get(node, []),
            *idx.partners.get(node, []),
        ):
            if nxt not in prev:
                prev[nxt] = node
                queue.append(nxt)
    return None


def _edge(idx: FamilyIndex, prev: uuid.UUID, cur: uuid.UUID) -> Edge:
    if cur in idx.parent_ids(prev):
        return "parent"
    if prev in idx.parent_ids(cur):
        return "child"
    return "partner"


InLawSide = Literal["partner_relative", "relative_partner"]


@dataclass(slots=True)
class Found:
    kind: KinshipKind
    path: list[uuid.UUID]
    blood: Blood | None = None
    side: InLawSide | None = None
    via: uuid.UUID | None = None


def _best_in_law(idx: FamilyIndex, a: uuid.UUID, b: uuid.UUID) -> Found | None:
    candidates: list[tuple[int, Found]] = []
    for partner in idx.partners.get(a, []):
        r = blood(idx, partner, b)
        if r:
            candidates.append(
                (r.up + r.down, Found("in_law", [a, *r.path], r, "partner_relative", partner))
            )
    for partner in idx.partners.get(b, []):
        r = blood(idx, a, partner)
        if r:
            candidates.append(
                (r.up + r.down, Found("in_law", [*r.path, b], r, "relative_partner", partner))
            )
    if not candidates:
        return None
    return min(candidates, key=lambda c: (c[0], c[1].side or ""))[1]


def find(idx: FamilyIndex, a: uuid.UUID, b: uuid.UUID) -> Found:
    if a == b:
        return Found("same", [a])
    if b in idx.partners.get(a, []):
        return Found("partner", [a, b])
    r = blood(idx, a, b)
    if r:
        return Found("blood", r.path, r)
    in_law = _best_in_law(idx, a, b)
    if in_law:
        return in_law
    path = _shortest_path(idx, a, b)
    return Found("distant", path) if path else Found("none", [])


async def relationship(
    session: AsyncSession, tree_id: uuid.UUID, a: uuid.UUID, b: uuid.UUID
) -> Relationship:
    idx = await load_index(session, tree_id)
    found = find(idx, a, b)
    ids: Iterable[uuid.UUID] = {a, b, *found.path, *(found.blood.common if found.blood else [])}
    people = await summary_map(session, tree_id, ids)
    if a not in people or b not in people:
        raise NotFoundError("person_not_found")
    r = found.blood
    return Relationship(
        a=people[a],
        b=people[b],
        kind=found.kind,
        up=r.up if r else None,
        down=r.down if r else None,
        half=r.half if r else False,
        non_biological=r.non_biological if r else False,
        side=found.side,
        via=people[found.via] if found.via else None,
        common_ancestors=[people[c] for c in r.common] if r and found.kind == "blood" else [],
        path=[
            PathStep(person=people[pid], edge=_edge(idx, prev, pid) if prev else None)
            for prev, pid in zip([None, *found.path], found.path, strict=False)
        ],
    )
