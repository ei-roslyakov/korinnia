"""One person's ancestors or descendants, for the fan, pedigree and descendancy charts
(D118). Built on the kinship index (all links of the tree in two queries), so the cost does
not grow with the number of generations asked for."""

from __future__ import annotations

import uuid
from collections import Counter

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Partnership, Person
from app.schemas.lineage import Direction, Lineage, LineageLink, LineagePartnership
from app.services.genealogy.kinship import FamilyIndex, load_index
from app.services.genealogy.persons import get_person
from app.services.genealogy.summaries import summaries_for
from app.services.visibility import Visibility


def _ancestors(
    idx: FamilyIndex, root: uuid.UUID, depth: int
) -> tuple[set[uuid.UUID], list[LineageLink], list[uuid.UUID], bool]:
    """Walk the pedigree as a tree (a person reached by two lines is visited twice, as the
    charts draw it), so repeated ancestors can be counted."""
    seen: Counter[uuid.UUID] = Counter({root: 1})
    links: dict[tuple[uuid.UUID, uuid.UUID], LineageLink] = {}
    frontier = [root]
    truncated = False
    for generation in range(depth + 1):
        nxt: list[uuid.UUID] = []
        for child in frontier:
            parents = idx.parents.get(child, [])
            if generation == depth:
                truncated = truncated or bool(parents)
                continue
            for parent, kind in parents:
                links[(parent, child)] = LineageLink(parent_id=parent, child_id=child, type=kind)
                seen[parent] += 1
                nxt.append(parent)
        frontier = nxt
    repeated = [pid for pid, n in seen.items() if n > 1]
    return set(seen), list(links.values()), repeated, truncated


def _descendants(
    idx: FamilyIndex, root: uuid.UUID, depth: int
) -> tuple[set[uuid.UUID], list[LineageLink], bool]:
    people = {root}
    links: dict[tuple[uuid.UUID, uuid.UUID], LineageLink] = {}
    frontier = [root]
    truncated = False
    for generation in range(depth + 1):
        nxt: list[uuid.UUID] = []
        for parent in frontier:
            children = idx.children.get(parent, [])
            if generation == depth:
                truncated = truncated or bool(children)
                continue
            for child in children:
                links[(parent, child)] = LineageLink(
                    parent_id=parent, child_id=child, type=idx.link_type(parent, child)
                )
                if child not in people:
                    people.add(child)
                    nxt.append(child)
        frontier = nxt
    # The other parent of each child (a partner), so couples can be shown together.
    for child in list(people - {root}):
        for parent, kind in idx.parents.get(child, []):
            if parent not in people and any(p in people for p in idx.partners.get(parent, [])):
                links[(parent, child)] = LineageLink(parent_id=parent, child_id=child, type=kind)
    return people, list(links.values()), truncated


async def lineage(
    session: AsyncSession,
    tree_id: uuid.UUID,
    person_id: uuid.UUID,
    direction: Direction,
    depth: int,
    seen: Visibility,
) -> Lineage:
    await get_person(session, tree_id, person_id)
    idx = await load_index(session, tree_id)
    partnerships: list[LineagePartnership] = []
    repeated: list[uuid.UUID] = []
    if direction == "ancestors":
        ids, links, repeated, truncated = _ancestors(idx, person_id, depth)
    else:
        ids, links, truncated = _descendants(idx, person_id, depth)
        lineal = set(ids)
        rows = await session.scalars(
            select(Partnership).where(
                Partnership.tree_id == tree_id,
                Partnership.deleted_at.is_(None),
                (Partnership.person_a_id.in_(lineal)) | (Partnership.person_b_id.in_(lineal)),
            )
        )
        for p in rows:
            if p.person_a_id not in idx.partners or p.person_b_id not in idx.partners:
                continue  # one of them is deleted
            ids |= {p.person_a_id, p.person_b_id}
            private = seen.hides_person(p.person_a_id) or seen.hides_person(p.person_b_id)
            partnerships.append(
                LineagePartnership(
                    id=p.id,
                    person_a_id=p.person_a_id,
                    person_b_id=p.person_b_id,
                    type=p.type,
                    year=None if private else p.start_date.year,
                )
            )
    persons = list(
        await session.scalars(select(Person).where(Person.id.in_(ids), Person.deleted_at.is_(None)))
    )
    return seen.redact(
        Lineage(
            root_id=person_id,
            direction=direction,
            depth=depth,
            persons=await summaries_for(session, tree_id, persons),
            parent_links=links,
            partnerships=partnerships,
            repeated=repeated,
            truncated=truncated,
        )
    )
