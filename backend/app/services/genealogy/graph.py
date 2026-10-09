"""The whole family graph of a tree (for the canvas): people + edges."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ParentChild, Partnership, Person, Place
from app.schemas.dates import PartialDateOut
from app.schemas.relationships import GraphEdge, GraphPartnership, TreeGraph
from app.services.genealogy.builder import layout_offsets
from app.services.genealogy.summaries import summaries_for


async def tree_graph(session: AsyncSession, tree_id: uuid.UUID) -> TreeGraph:
    persons = list(
        await session.scalars(
            select(Person).where(Person.tree_id == tree_id, Person.deleted_at.is_(None))
        )
    )
    live = {p.id for p in persons}
    summaries = await summaries_for(session, tree_id, persons, whole_tree=True)
    links = await session.scalars(
        select(ParentChild).where(ParentChild.tree_id == tree_id, ParentChild.deleted_at.is_(None))
    )
    partnerships = list(
        await session.scalars(
            select(Partnership).where(
                Partnership.tree_id == tree_id, Partnership.deleted_at.is_(None)
            )
        )
    )
    place_ids = {p.place_id for p in partnerships if p.place_id}
    places = (
        dict(
            (
                await session.execute(select(Place.id, Place.name).where(Place.id.in_(place_ids)))
            ).all()
        )
        if place_ids
        else {}
    )
    offsets = await layout_offsets(session, tree_id)
    return TreeGraph(
        layout_offsets={pid: o for pid, o in offsets.items() if pid in live},
        persons=summaries,
        parent_child=[
            GraphEdge(id=e.id, parent_id=e.parent_id, child_id=e.child_id, type=e.type)
            for e in links
            if e.parent_id in live and e.child_id in live
        ],
        partnerships=[
            GraphPartnership(
                id=p.id,
                person_a_id=p.person_a_id,
                person_b_id=p.person_b_id,
                type=p.type,
                start_date=PartialDateOut.from_domain(p.start_date),
                end_date=PartialDateOut.from_domain(p.end_date),
                end_reason=p.end_reason,
                place=places.get(p.place_id) if p.place_id else None,
            )
            for p in partnerships
            if p.person_a_id in live and p.person_b_id in live
        ],
    )
