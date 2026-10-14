"""User administration, invitations, password-reset links, superadmin bootstrap."""

from __future__ import annotations

import logging
import uuid
from datetime import timedelta

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings, get_settings
from app.core.errors import AppError, ConflictError, NotFoundError
from app.core.security import generate_url_token, hash_password, hash_token, utcnow
from app.models import (
    Invitation,
    Language,
    PasswordResetToken,
    Tree,
    TreeMembership,
    TreeRole,
    User,
)
from app.services import audit
from app.services.auth import clear_totp, get_user_by_email, revoke_all_sessions
from app.services.context import Actor

logger = logging.getLogger(__name__)

USER_AUDIT_FIELDS = (
    "email",
    "display_name",
    "preferred_language",
    "is_superadmin",
    "is_active",
    "can_create_trees",
    "totp_enabled",
)
INVITATION_AUDIT_FIELDS = ("email", "tree_id", "role", "is_superadmin", "expires_at")


def link(path: str) -> str:
    return f"{get_settings().public_base_url.rstrip('/')}{path}"


# --- Users ------------------------------------------------------------------------------


async def list_users(
    session: AsyncSession, *, q: str | None, is_active: bool | None, limit: int, offset: int
) -> tuple[list[User], int]:
    stmt = select(User).where(User.is_sandbox.is_(False))  # demo accounts come and go
    if q:
        like = f"%{q.strip().lower()}%"
        stmt = stmt.where(
            or_(func.lower(User.email).like(like), func.lower(User.display_name).like(like))
        )
    if is_active is not None:
        stmt = stmt.where(User.is_active.is_(is_active))
    total = await session.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = await session.scalars(
        stmt.order_by(func.lower(User.display_name), User.id).limit(limit).offset(offset)
    )
    return list(rows), total or 0


async def get_user(session: AsyncSession, user_id: uuid.UUID) -> User:
    user = await session.get(User, user_id)
    if user is None:
        raise NotFoundError("user_not_found")
    return user


async def create_user(
    session: AsyncSession,
    *,
    email: str,
    display_name: str,
    password: str | None,
    preferred_language: Language | None = None,
    is_superadmin: bool = False,
    actor: Actor,
    commit: bool = True,
) -> User:
    if await get_user_by_email(session, email):
        raise ConflictError("email_taken")
    user = User(
        email=email.strip().lower(),
        display_name=display_name.strip(),
        password_hash=hash_password(password) if password else None,
        preferred_language=preferred_language or get_settings().default_language,
        is_superadmin=is_superadmin,
    )
    session.add(user)
    await session.flush()
    audit.record(
        session,
        actor,
        "user.create",
        "user",
        user.id,
        after=audit.snapshot(user, USER_AUDIT_FIELDS),
    )
    if commit:
        await session.commit()
        await _after_user_created(user)
    return user


async def _after_user_created(user: User) -> None:
    """Queue the user's own demo family (when enabled). Call after the user is committed."""
    if get_settings().demo_tree_for_new_users:
        from app.jobs.queue import enqueue_demo_tree  # jobs import services; avoid a cycle

        await enqueue_demo_tree(user.id)


async def _active_superadmins(session: AsyncSession) -> int:
    count = await session.scalar(
        select(func.count()).where(User.is_superadmin.is_(True), User.is_active.is_(True))
    )
    return count or 0


def may_create_trees(user: User) -> bool:
    """Superadmins always; others when the installation allows it and it is not turned off
    for them."""
    if user.is_superadmin:
        return True
    return get_settings().users_can_create_trees and user.can_create_trees


async def update_user(
    session: AsyncSession,
    target: User,
    *,
    display_name: str | None,
    preferred_language: Language | None,
    is_active: bool | None,
    is_superadmin: bool | None,
    actor: Actor,
    can_create_trees: bool | None = None,
) -> User:
    is_self = actor.user is not None and actor.user.id == target.id
    losing_superadmin = (is_active is False or is_superadmin is False) and target.is_superadmin
    if is_self and (is_active is False or is_superadmin is False):
        raise AppError("cannot_demote_self")
    if losing_superadmin and target.is_active and await _active_superadmins(session) <= 1:
        raise AppError("last_superadmin")

    before = audit.snapshot(target, USER_AUDIT_FIELDS)
    if display_name is not None:
        target.display_name = display_name.strip()
    if preferred_language is not None:
        target.preferred_language = preferred_language
    if is_superadmin is not None:
        target.is_superadmin = is_superadmin
    if can_create_trees is not None:
        target.can_create_trees = can_create_trees
    if is_active is not None and is_active != target.is_active:
        target.is_active = is_active
        if not is_active:
            await revoke_all_sessions(session, target)
    after = audit.snapshot(target, USER_AUDIT_FIELDS)
    if before != after:
        b, a = audit.diff_only(before, after)
        audit.record(session, actor, "user.update", "user", target.id, before=b, after=a)
    await session.commit()
    return target


async def delete_user(session: AsyncSession, target: User, actor: Actor) -> None:
    if actor.user is not None and actor.user.id == target.id:
        raise AppError("cannot_delete_self")
    if target.is_superadmin and target.is_active and await _active_superadmins(session) <= 1:
        raise AppError("last_superadmin")
    audit.record(
        session,
        actor,
        "user.delete",
        "user",
        target.id,
        before=audit.snapshot(target, USER_AUDIT_FIELDS),
    )
    await session.delete(target)
    await session.commit()


async def admin_disable_2fa(session: AsyncSession, target: User, actor: Actor) -> None:
    """For a user who lost their authenticator device and recovery codes."""
    await clear_totp(session, target)
    audit.record(session, actor, "user.2fa_reset", "user", target.id)
    await session.commit()


# --- Password reset links ---------------------------------------------------------------


async def create_password_reset(
    session: AsyncSession, target: User, actor: Actor
) -> tuple[str, PasswordResetToken]:
    now = utcnow()
    # Only the newest link works.
    await session.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.user_id == target.id, PasswordResetToken.used_at.is_(None))
        .values(used_at=now)
    )
    token = generate_url_token()
    row = PasswordResetToken(
        token_hash=hash_token(token),
        user_id=target.id,
        created_by_id=actor.user.id if actor.user else None,
        expires_at=now + timedelta(hours=get_settings().password_reset_ttl_hours),
    )
    session.add(row)
    audit.record(session, actor, "user.password_reset_link", "user", target.id)
    await session.commit()
    return link(f"/reset-password/{token}"), row


async def get_password_reset(session: AsyncSession, token: str) -> PasswordResetToken:
    row = (
        await session.scalars(
            select(PasswordResetToken)
            .options(selectinload(PasswordResetToken.user))
            .where(PasswordResetToken.token_hash == hash_token(token))
        )
    ).first()
    if row is None or row.used_at is not None or row.expires_at <= utcnow():
        raise NotFoundError("link_invalid")
    if not row.user.is_active:
        raise NotFoundError("link_invalid")
    return row


async def consume_password_reset(
    session: AsyncSession, token: str, password: str, actor: Actor
) -> User:
    row = await get_password_reset(session, token)
    user = row.user
    row.used_at = utcnow()
    user.password_hash = hash_password(password)
    await revoke_all_sessions(session, user)
    audit.record(session, Actor(user, actor.ip), "user.password_reset", "user", user.id)
    await session.commit()
    return user


# --- Invitations ------------------------------------------------------------------------


async def create_invitation(
    session: AsyncSession,
    *,
    email: str,
    tree: Tree | None,
    role: TreeRole | None,
    is_superadmin: bool,
    actor: Actor,
) -> tuple[Invitation, str]:
    email = email.strip().lower()
    if await get_user_by_email(session, email):
        raise ConflictError("email_taken")
    now = utcnow()
    same_tree = Invitation.tree_id == tree.id if tree else Invitation.tree_id.is_(None)
    # Re-inviting replaces the previous pending invitation for the same email and tree.
    await session.execute(
        update(Invitation)
        .where(
            func.lower(Invitation.email) == email,
            same_tree,
            Invitation.accepted_at.is_(None),
            Invitation.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    token = generate_url_token()
    inv = Invitation(
        token_hash=hash_token(token),
        email=email,
        tree_id=tree.id if tree else None,
        role=role,
        is_superadmin=is_superadmin,
        created_by_id=actor.user.id if actor.user else None,
        expires_at=now + timedelta(hours=get_settings().invitation_ttl_hours),
    )
    session.add(inv)
    await session.flush()
    audit.record(
        session,
        actor,
        "invitation.create",
        "invitation",
        inv.id,
        tree_id=inv.tree_id,
        after=audit.snapshot(inv, INVITATION_AUDIT_FIELDS),
    )
    await session.commit()
    await session.refresh(inv, ["tree", "created_by"])
    return inv, link(f"/invite/{token}")


async def list_invitations(
    session: AsyncSession, *, tree_id: uuid.UUID | None = None, pending_only: bool = True
) -> list[Invitation]:
    stmt = select(Invitation).options(
        selectinload(Invitation.tree), selectinload(Invitation.created_by)
    )
    if tree_id is not None:
        stmt = stmt.where(Invitation.tree_id == tree_id)
    if pending_only:
        stmt = stmt.where(
            Invitation.accepted_at.is_(None),
            Invitation.revoked_at.is_(None),
            Invitation.expires_at > utcnow(),
        )
    rows = await session.scalars(stmt.order_by(Invitation.created_at.desc()))
    return list(rows)


async def get_invitation(session: AsyncSession, invitation_id: uuid.UUID) -> Invitation:
    inv = await session.get(Invitation, invitation_id)
    if inv is None:
        raise NotFoundError("invitation_not_found")
    return inv


async def get_valid_invitation(session: AsyncSession, token: str) -> Invitation:
    inv = (
        await session.scalars(
            select(Invitation)
            .options(selectinload(Invitation.tree))
            .where(Invitation.token_hash == hash_token(token))
        )
    ).first()
    if (
        inv is None
        or inv.accepted_at is not None
        or inv.revoked_at is not None
        or inv.expires_at <= utcnow()
        or (inv.tree is not None and inv.tree.deleted_at is not None)
    ):
        raise NotFoundError("link_invalid")
    return inv


async def accept_invitation(
    session: AsyncSession,
    token: str,
    *,
    display_name: str,
    password: str,
    preferred_language: Language | None,
    actor: Actor,
) -> User:
    inv = await get_valid_invitation(session, token)
    user = await create_user(
        session,
        email=inv.email,
        display_name=display_name,
        password=password,
        preferred_language=preferred_language,
        is_superadmin=inv.is_superadmin,
        actor=actor,
        commit=False,
    )
    new_actor = Actor(user, actor.ip, actor.user_agent)
    if inv.tree_id is not None and inv.role is not None:
        session.add(TreeMembership(tree_id=inv.tree_id, user_id=user.id, role=inv.role))
        audit.record(
            session,
            new_actor,
            "membership.add",
            "membership",
            user.id,
            tree_id=inv.tree_id,
            after={"user_id": str(user.id), "role": inv.role.value},
        )
    inv.accepted_at = utcnow()
    inv.accepted_user_id = user.id
    audit.record(session, new_actor, "invitation.accept", "invitation", inv.id, tree_id=inv.tree_id)
    await session.commit()
    await _after_user_created(user)
    return user


async def revoke_invitation(session: AsyncSession, inv: Invitation, actor: Actor) -> None:
    if inv.accepted_at is not None:
        raise AppError("invitation_already_accepted")
    if inv.revoked_at is None:
        inv.revoked_at = utcnow()
        audit.record(session, actor, "invitation.revoke", "invitation", inv.id, tree_id=inv.tree_id)
        await session.commit()


# --- Bootstrap --------------------------------------------------------------------------


async def bootstrap_superadmin(session: AsyncSession, settings: Settings) -> User | None:
    """Create the first superadmin from SUPERADMIN_EMAIL / SUPERADMIN_PASSWORD.

    Does nothing if any superadmin already exists, so it is safe to run on every start and
    changing the env vars later never overrides credentials set in the app.
    """
    if not settings.superadmin_email or not settings.superadmin_password:
        return None
    existing = await session.scalar(select(func.count()).where(User.is_superadmin.is_(True)))
    if existing:
        return None
    password = settings.superadmin_password.get_secret_value()
    if len(password) < settings.password_min_length:
        raise AppError("superadmin_password_too_short")
    user = await get_user_by_email(session, settings.superadmin_email)
    actor = Actor(None)
    if user is not None:
        user.is_superadmin = True
        user.is_active = True
        audit.record(session, actor, "user.promote_superadmin", "user", user.id)
        await session.commit()
        logger.info("existing user promoted to superadmin", extra={"email": user.email})
        return user
    user = await create_user(
        session,
        email=settings.superadmin_email,
        display_name=settings.superadmin_email.split("@")[0],
        password=password,
        is_superadmin=True,
        actor=actor,
    )
    logger.info("superadmin created", extra={"email": user.email})
    return user
