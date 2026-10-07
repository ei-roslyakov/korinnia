"""Parent–child links and partnerships, with hard validation (errors) and soft warnings."""

from __future__ import annotations

import uuid

from sqlalchemy import func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, ConflictError
from app.core.security import utcnow
from app.models import ParentChild, ParentChildType, Partnership, Person
from app.schemas.persons import Warning
from app.schemas.relationships import (
    ParentChildCreate,
    ParentChildUpdate,
    PartnershipCreate,
    PartnershipUpdate,
)
from app.services import audit
from app.services.context import Actor
from app.services.genealogy.common import check_place, get_live, set_date, to_partial
from app.services.genealogy.plausibility import link_warnings
from app.services.genealogy.snapshots import parent_child_snapshot, partnership_snapshot

MAX_BIOLOGICAL_PARENTS = 2


async def ancestors_of(session: AsyncSession, person_id: uuid.UUID) -> set[uuid.UUID]:
    """All ancestors via live parent links (recursive CTE; cycle-safe via UNION)."""
    anc = (
        select(ParentChild.parent_id.label("id"))
        .where(ParentChild.child_id == person_id, ParentChild.deleted_at.is_(None))
        .cte("ancestors", recursive=True)
    )
    anc = anc.union(
        select(ParentChild.parent_id).where(
            ParentChild.child_id == anc.c.id, ParentChild.deleted_at.is_(None)
        )
    )
    return set(await session.scalars(select(anc.c.id)))


async def _biological_parent_count(
    session: AsyncSession, child_id: uuid.UUID, exclude: uuid.UUID | None = None
) -> int:
    stmt = select(func.count()).where(
        ParentChild.child_id == child_id,
        ParentChild.type == ParentChildType.biological,
        ParentChild.deleted_at.is_(None),
    )
    if exclude is not None:
        stmt = stmt.where(ParentChild.id != exclude)
    return await session.scalar(stmt) or 0


async def _person(session: AsyncSession, tree_id: uuid.UUID, pid: uuid.UUID) -> Person:
    return await get_live(session, Person, tree_id, pid, "person_not_found")


async def create_parent_child(
    session: AsyncSession, tree_id: uuid.UUID, body: ParentChildCreate, actor: Actor
) -> tuple[ParentChild, list[Warning]]:
    if body.parent_id == body.child_id:
        raise AppError("self_relation")
    parent = await _person(session, tree_id, body.parent_id)
    await _person(session, tree_id, body.child_id)
    duplicate = await session.scalar(
        select(literal(1)).where(
            ParentChild.parent_id == body.parent_id,
            ParentChild.child_id == body.child_id,
            ParentChild.deleted_at.is_(None),
        )
    )
    if duplicate:
        raise ConflictError("relationship_exists")
    if body.child_id in await ancestors_of(session, body.parent_id):
        raise ConflictError("relationship_cycle")
    if (
        body.type == ParentChildType.biological
        and await _biological_parent_count(session, body.child_id) >= MAX_BIOLOGICAL_PARENTS
    ):
        raise ConflictError("too_many_biological_parents")
    user_id = actor.user.id if actor.user else None
    link = ParentChild(
        id=uuid.uuid4(),
        tree_id=tree_id,
        parent_id=body.parent_id,
        child_id=body.child_id,
        type=body.type,
        notes=body.notes,
        created_by_id=user_id,
        updated_by_id=user_id,
    )
    session.add(link)
    await session.flush()
    audit.record(
        session,
        actor,
        "parent_child.create",
        "parent_child",
        link.id,
        tree_id=tree_id,
        after=parent_child_snapshot(link),
    )
    warnings = await link_warnings(session, tree_id, parent, body.child_id)
    await session.commit()
    return link, warnings


async def get_parent_child(
    session: AsyncSession, tree_id: uuid.UUID, link_id: uuid.UUID
) -> ParentChild:
    return await get_live(session, ParentChild, tree_id, link_id, "relationship_not_found")


async def update_parent_child(
    session: AsyncSession, link: ParentChild, body: ParentChildUpdate, actor: Actor
) -> tuple[ParentChild, list[Warning]]:
    before = parent_child_snapshot(link)
    if (
        body.type == ParentChildType.biological
        and link.type != ParentChildType.biological
        and await _biological_parent_count(session, link.child_id, exclude=link.id)
        >= MAX_BIOLOGICAL_PARENTS
    ):
        raise ConflictError("too_many_biological_parents")
    if body.type is not None:
        link.type = body.type
    if "notes" in body.model_fields_set:
        link.notes = body.notes
    link.updated_by_id = actor.user.id if actor.user else None
    after = parent_child_snapshot(link)
    if before != after:
        audit.record(
            session,
            actor,
            "parent_child.update",
            "parent_child",
            link.id,
            tree_id=link.tree_id,
            before=before,
            after=after,
        )
    parent = await _person(session, link.tree_id, link.parent_id)
    warnings = await link_warnings(session, link.tree_id, parent, link.child_id)
    await session.commit()
    return link, warnings


async def delete_parent_child(session: AsyncSession, link: ParentChild, actor: Actor) -> None:
    link.deleted_at = utcnow()
    link.deleted_batch_id = link.id
    audit.record(
        session,
        actor,
        "parent_child.delete",
        "parent_child",
        link.id,
        tree_id=link.tree_id,
        before=parent_child_snapshot(link),
    )
    await session.commit()


# --- Partnerships -----------------------------------------------------------------------


async def create_partnership(
    session: AsyncSession, tree_id: uuid.UUID, body: PartnershipCreate, actor: Actor
) -> Partnership:
    if body.person_a_id == body.person_b_id:
        raise AppError("self_relation")
    await _person(session, tree_id, body.person_a_id)
    await _person(session, tree_id, body.person_b_id)
    await check_place(session, tree_id, body.place_id)
    user_id = actor.user.id if actor.user else None
    p = Partnership(
        id=uuid.uuid4(),
        tree_id=tree_id,
        person_a_id=body.person_a_id,
        person_b_id=body.person_b_id,
        end_reason=body.end_reason,
        place_id=body.place_id,
        notes=body.notes,
        created_by_id=user_id,
        updated_by_id=user_id,
    )
    if body.type is not None:
        p.type = body.type
    set_date(p, "start_date", "start_sort", to_partial(body.start_date))
    set_date(p, "end_date", "end_sort", to_partial(body.end_date))
    session.add(p)
    await session.flush()
    audit.record(
        session,
        actor,
        "partnership.create",
        "partnership",
        p.id,
        tree_id=tree_id,
        after=partnership_snapshot(p),
    )
    await session.commit()
    await session.refresh(p)
    return p


async def get_partnership(session: AsyncSession, tree_id: uuid.UUID, pid: uuid.UUID) -> Partnership:
    return await get_live(session, Partnership, tree_id, pid, "relationship_not_found")


async def update_partnership(
    session: AsyncSession, p: Partnership, body: PartnershipUpdate, actor: Actor
) -> Partnership:
    before = partnership_snapshot(p)
    fields = body.model_fields_set
    if body.type is not None:
        p.type = body.type
    if "start_date" in fields:
        set_date(p, "start_date", "start_sort", to_partial(body.start_date))
    if "end_date" in fields:
        set_date(p, "end_date", "end_sort", to_partial(body.end_date))
    if "end_reason" in fields:
        p.end_reason = body.end_reason
    if "place_id" in fields:
        await check_place(session, p.tree_id, body.place_id)
        p.place_id = body.place_id
    if "notes" in fields:
        p.notes = body.notes
    p.updated_by_id = actor.user.id if actor.user else None
    after = partnership_snapshot(p)
    if before != after:
        audit.record(
            session,
            actor,
            "partnership.update",
            "partnership",
            p.id,
            tree_id=p.tree_id,
            before=before,
            after=after,
        )
    await session.commit()
    await session.refresh(p)
    return p


async def delete_partnership(session: AsyncSession, p: Partnership, actor: Actor) -> None:
    p.deleted_at = utcnow()
    p.deleted_batch_id = p.id
    audit.record(
        session,
        actor,
        "partnership.delete",
        "partnership",
        p.id,
        tree_id=p.tree_id,
        before=partnership_snapshot(p),
    )
    await session.commit()
