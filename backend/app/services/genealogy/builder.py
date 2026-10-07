"""Composite builder operations and canvas layout offsets."""

from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models import LayoutOffset, ParentChild, Person
from app.schemas.persons import PersonCreate
from app.schemas.relationships import LayoutOffset as LayoutOffsetIn
from app.schemas.relationships import ParentChildCreate, PartnershipCreate
from app.services.context import Actor
from app.services.genealogy.common import get_live
from app.services.genealogy.persons import create_person
from app.services.genealogy.relationships import create_parent_child, create_partnership


async def _live_parent_ids(session: AsyncSession, person_id: uuid.UUID) -> list[uuid.UUID]:
    return list(
        await session.scalars(
            select(ParentChild.parent_id).where(
                ParentChild.child_id == person_id, ParentChild.deleted_at.is_(None)
            )
        )
    )


async def create_person_with_relative(
    session: AsyncSession, tree_id: uuid.UUID, body: PersonCreate, actor: Actor
) -> Person:
    """Create a person and, optionally, link them to a relative — all or nothing."""
    link = body.relative
    if link is None:
        return await create_person(session, tree_id, body, actor)

    async with session.begin_nested():  # any validation error rolls everything back
        relative = await get_live(session, Person, tree_id, link.person_id, "person_not_found")
        person = await create_person(session, tree_id, body, actor, commit=False)

        async def parent_link(parent: uuid.UUID, child: uuid.UUID) -> None:
            await create_parent_child(
                session,
                tree_id,
                ParentChildCreate(parent_id=parent, child_id=child, type=link.parent_child_type),
                actor,
                commit=False,
            )

        async def partnership(a: uuid.UUID, b: uuid.UUID) -> None:
            await create_partnership(
                session,
                tree_id,
                PartnershipCreate(person_a_id=a, person_b_id=b, type=link.partnership_type),
                actor,
                commit=False,
            )

        match link.relation:
            case "parent":
                existing_parents = await _live_parent_ids(session, relative.id)
                if link.other_parent_id and link.other_parent_id not in existing_parents:
                    raise AppError("invalid_other_parent")
                await parent_link(person.id, relative.id)
                if link.other_parent_id:
                    await partnership(link.other_parent_id, person.id)
            case "child":
                await parent_link(relative.id, person.id)
                if link.other_parent_id:
                    await get_live(
                        session, Person, tree_id, link.other_parent_id, "person_not_found"
                    )
                    await parent_link(link.other_parent_id, person.id)
            case "partner":
                await partnership(relative.id, person.id)
            case "sibling":
                parents = await _live_parent_ids(session, relative.id)
                if not parents:
                    raise AppError("sibling_needs_parents")
                for parent_id in parents:
                    await parent_link(parent_id, person.id)
    await session.commit()
    return person


# --- Layout offsets ---------------------------------------------------------------------


async def layout_offsets(
    session: AsyncSession, tree_id: uuid.UUID
) -> dict[uuid.UUID, LayoutOffsetIn]:
    rows = await session.scalars(select(LayoutOffset).where(LayoutOffset.tree_id == tree_id))
    return {r.person_id: LayoutOffsetIn(dx=r.dx, dy=r.dy) for r in rows}


async def set_layout_offset(
    session: AsyncSession, tree_id: uuid.UUID, person_id: uuid.UUID, offset: LayoutOffsetIn
) -> None:
    await get_live(session, Person, tree_id, person_id, "person_not_found")
    if offset.dx == 0 and offset.dy == 0:
        await session.execute(
            delete(LayoutOffset).where(
                LayoutOffset.tree_id == tree_id, LayoutOffset.person_id == person_id
            )
        )
    else:
        stmt = insert(LayoutOffset).values(
            tree_id=tree_id, person_id=person_id, dx=offset.dx, dy=offset.dy
        )
        await session.execute(
            stmt.on_conflict_do_update(
                index_elements=["tree_id", "person_id"],
                set_={"dx": offset.dx, "dy": offset.dy},
            )
        )
    await session.commit()


async def reset_layout(session: AsyncSession, tree_id: uuid.UUID) -> None:
    await session.execute(delete(LayoutOffset).where(LayoutOffset.tree_id == tree_id))
    await session.commit()
