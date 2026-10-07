"""Trees and per-tree membership / roles."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload

from app.core.errors import AppError, NotFoundError
from app.core.security import utcnow
from app.models import Invitation, Tree, TreeMembership, TreeRole, User
from app.services import audit
from app.services.auth import get_user_by_email
from app.services.context import Actor
from app.services.users import create_invitation

TREE_AUDIT_FIELDS = ("name", "description", "owner_id", "deleted_at")


async def list_trees_for_user(session: AsyncSession, user: User) -> list[tuple[Tree, TreeRole]]:
    """Trees the user can open, with their effective role (superadmins: admin everywhere)."""
    if user.is_superadmin:
        # Every tree, except other people's personal copies of the demo family.
        trees = await session.scalars(
            select(Tree)
            .where(
                Tree.deleted_at.is_(None),
                or_(Tree.is_demo.is_(False), Tree.owner_id == user.id),
            )
            .order_by(func.lower(Tree.name))
        )
        return [(t, TreeRole.admin) for t in trees]
    rows = await session.execute(
        select(Tree, TreeMembership.role)
        .join(TreeMembership, TreeMembership.tree_id == Tree.id)
        .where(TreeMembership.user_id == user.id, Tree.deleted_at.is_(None))
        .order_by(func.lower(Tree.name))
    )
    return [(tree, role) for tree, role in rows]


async def get_tree_role(
    session: AsyncSession, tree_id: uuid.UUID, user: User
) -> tuple[Tree, TreeRole] | None:
    tree = await session.get(Tree, tree_id)
    if tree is None or tree.deleted_at is not None:
        return None
    if user.is_superadmin:
        return tree, TreeRole.admin
    membership = await session.get(TreeMembership, (tree_id, user.id))
    return (tree, membership.role) if membership else None


async def create_tree(
    session: AsyncSession,
    *,
    name: str,
    description: str | None,
    owner: User,
    actor: Actor,
    is_demo: bool = False,
) -> Tree:
    tree = Tree(name=name.strip(), description=description, owner_id=owner.id, is_demo=is_demo)
    session.add(tree)
    await session.flush()
    session.add(TreeMembership(tree_id=tree.id, user_id=owner.id, role=TreeRole.admin))
    audit.record(
        session,
        actor,
        "tree.create",
        "tree",
        tree.id,
        tree_id=tree.id,
        after=audit.snapshot(tree, TREE_AUDIT_FIELDS),
    )
    await session.commit()
    return tree


async def update_tree(
    session: AsyncSession,
    tree: Tree,
    *,
    name: str | None,
    description: str | None,
    fields_set: set[str],
    actor: Actor,
) -> Tree:
    before = audit.snapshot(tree, TREE_AUDIT_FIELDS)
    if name is not None:
        tree.name = name.strip()
    if "description" in fields_set:
        tree.description = description
    after = audit.snapshot(tree, TREE_AUDIT_FIELDS)
    if before != after:
        b, a = audit.diff_only(before, after)
        audit.record(
            session, actor, "tree.update", "tree", tree.id, tree_id=tree.id, before=b, after=a
        )
    await session.commit()
    await session.refresh(tree)
    return tree


async def delete_tree(session: AsyncSession, tree: Tree, actor: Actor) -> None:
    """Soft delete: the tree disappears from the UI but no data is destroyed."""
    tree.deleted_at = utcnow()
    audit.record(session, actor, "tree.delete", "tree", tree.id, tree_id=tree.id)
    await session.commit()


# --- Members ----------------------------------------------------------------------------


async def list_members(session: AsyncSession, tree: Tree) -> list[tuple[TreeMembership, User]]:
    rows = await session.execute(
        select(TreeMembership, User)
        .join(User, User.id == TreeMembership.user_id)
        .where(TreeMembership.tree_id == tree.id)
        .order_by(func.lower(User.display_name))
    )
    return [(m, u) for m, u in rows]


async def _admin_count(session: AsyncSession, tree_id: uuid.UUID) -> int:
    count = await session.scalar(
        select(func.count())
        .select_from(TreeMembership)
        .join(User, User.id == TreeMembership.user_id)
        .where(
            TreeMembership.tree_id == tree_id,
            TreeMembership.role == TreeRole.admin,
            User.is_active.is_(True),
        )
    )
    return count or 0


async def _ensure_not_last_admin(session: AsyncSession, membership: TreeMembership) -> None:
    if membership.role == TreeRole.admin and await _admin_count(session, membership.tree_id) <= 1:
        raise AppError("last_tree_admin")


async def add_member_or_invite(
    session: AsyncSession, tree: Tree, *, email: str, role: TreeRole, actor: Actor
) -> tuple[TreeMembership | None, User | None, Invitation | None, str | None]:
    """Add an existing user to the tree, or create an invitation for a new email."""
    user = await get_user_by_email(session, email)
    if user is None:
        inv, url = await create_invitation(
            session, email=email, tree=tree, role=role, is_superadmin=False, actor=actor
        )
        return None, None, inv, url
    existing = await session.get(TreeMembership, (tree.id, user.id))
    if existing is not None:
        raise AppError("already_member", status_code=409)
    membership = TreeMembership(tree_id=tree.id, user_id=user.id, role=role)
    session.add(membership)
    audit.record(
        session,
        actor,
        "membership.add",
        "membership",
        user.id,
        tree_id=tree.id,
        after={"user_id": str(user.id), "role": role.value},
    )
    await session.commit()
    await session.refresh(membership)
    return membership, user, None, None


async def get_membership(session: AsyncSession, tree: Tree, user_id: uuid.UUID) -> TreeMembership:
    membership = await session.get(
        TreeMembership, (tree.id, user_id), options=[selectinload(TreeMembership.user)]
    )
    if membership is None:
        raise NotFoundError("member_not_found")
    return membership


async def update_member_role(
    session: AsyncSession, membership: TreeMembership, role: TreeRole, actor: Actor
) -> TreeMembership:
    if membership.role == role:
        return membership
    if role != TreeRole.admin:
        await _ensure_not_last_admin(session, membership)
    before = {"role": membership.role.value}
    membership.role = role
    audit.record(
        session,
        actor,
        "membership.update",
        "membership",
        membership.user_id,
        tree_id=membership.tree_id,
        before=before,
        after={"role": role.value},
    )
    await session.commit()
    await session.refresh(membership)
    return membership


async def remove_member(session: AsyncSession, membership: TreeMembership, actor: Actor) -> None:
    await _ensure_not_last_admin(session, membership)
    audit.record(
        session,
        actor,
        "membership.remove",
        "membership",
        membership.user_id,
        tree_id=membership.tree_id,
        before={"user_id": str(membership.user_id), "role": membership.role.value},
    )
    await session.delete(membership)
    await session.commit()


@dataclass(slots=True)
class Overview:
    person_count: int = 0
    first_year: int | None = None
    last_year: int | None = None
    cover: list[str] = field(default_factory=list)


COVER_SIZE = 4


async def overviews(session: AsyncSession, tree_ids: list[uuid.UUID]) -> dict[uuid.UUID, Overview]:
    """People count, years covered and a few portraits per tree, in three queries."""
    from app.models import Event, Person
    from app.services.genealogy.media_urls import avatar_url

    out = {tid: Overview() for tid in tree_ids}
    if not tree_ids:
        return out
    for tid, count in await session.execute(
        select(Person.tree_id, func.count())
        .where(Person.tree_id.in_(tree_ids), Person.deleted_at.is_(None))
        .group_by(Person.tree_id)
    ):
        out[tid].person_count = count
    for tid, first, last in await session.execute(
        select(Event.tree_id, func.min(Event.date_sort), func.max(Event.date_sort))
        .where(Event.tree_id.in_(tree_ids), Event.deleted_at.is_(None))
        .group_by(Event.tree_id)
    ):
        out[tid].first_year = first.year if first else None
        out[tid].last_year = last.year if last else None
    ranked = (
        select(
            Person,
            func.row_number()
            .over(partition_by=Person.tree_id, order_by=(Person.created_at, Person.id))
            .label("n"),
        )
        .where(
            Person.tree_id.in_(tree_ids),
            Person.deleted_at.is_(None),
            Person.avatar_key.is_not(None),
        )
        .subquery()
    )
    person = aliased(Person, ranked)
    for p in await session.scalars(select(person).where(ranked.c.n <= COVER_SIZE)):
        url = avatar_url(p, None)
        if url:
            out[p.tree_id].cover.append(url)
    return out
