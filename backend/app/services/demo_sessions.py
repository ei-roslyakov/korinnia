"""Public demo login: a throwaway account with a fresh copy of the demo family per sign-in.

Everyone signs in with the same published demo credentials, but each sign-in gets its own
hidden account (`users.is_sandbox`), so visitors never see each other's changes. The session
lasts DEMO_SESSION_TIMEOUT_MINUTES and cannot be extended; once it has ended, `purge_ended`
(a worker job every few minutes) deletes the account with its trees and stored files.
"""

from __future__ import annotations

import logging
import uuid
from datetime import timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError, TooManyRequestsError
from app.core.security import tokens_equal, utcnow
from app.models import AuditLog, LoginAttempt, RefreshToken, Tree, User
from app.services import audit
from app.services.auth import SessionTokens, record_attempt, start_session
from app.services.context import Actor
from app.storage import Storage

logger = logging.getLogger(__name__)

# Stored files of a tree live under these prefixes (see media / imports services).
_TREE_PREFIXES = ("originals", "derived", "avatars", "imports")


def is_demo_login(email: str, password: str) -> bool:
    s = get_settings()
    return (
        s.demo_login_enabled
        and email.strip().lower() == s.demo_login_email.strip().lower()
        and tokens_equal(password, s.demo_login_password.get_secret_value())
    )


async def _check_limits(session: AsyncSession, ip: str | None) -> None:
    s = get_settings()
    demo_email = s.demo_login_email.strip().lower()
    if ip:
        hour_ago = utcnow() - timedelta(hours=1)
        recent, oldest = (
            await session.execute(
                select(func.count(), func.min(LoginAttempt.created_at)).where(
                    LoginAttempt.email == demo_email,
                    LoginAttempt.ip_address == ip,
                    LoginAttempt.success.is_(True),
                    LoginAttempt.created_at >= hour_ago,
                )
            )
        ).one()
        if recent >= s.demo_logins_per_ip_per_hour:
            retry = int(((oldest or utcnow()) + timedelta(hours=1) - utcnow()).total_seconds())
            raise TooManyRequestsError(max(retry, 1))
    active = await session.scalar(select(func.count()).where(User.is_sandbox.is_(True)))
    if (active or 0) >= s.demo_max_active:
        raise AppError("demo_busy", status_code=503)


async def start_demo(
    session: AsyncSession, actor: Actor, *, storage: Storage | None = None
) -> tuple[User, SessionTokens]:
    """Create a demo account with its own demo family and sign it in."""
    from app import seed as demo  # the demo data imports most services; load lazily

    await _check_limits(session, actor.ip)
    s = get_settings()
    short = uuid.uuid4().hex[:12]
    user = User(
        email=f"demo-{short}@sandbox.invalid",
        display_name="Demo",
        preferred_language=s.default_language,
        is_sandbox=True,
        can_create_trees=True,
        # Seen already: the demo shows the app, not our onboarding popups.
        welcome_dismissed=False,
    )
    session.add(user)
    await session.commit()
    await demo.seed(session, user, storage=storage)
    await record_attempt(session, s.demo_login_email.strip().lower(), actor.ip, success=True)
    audit.record(session, Actor(user, actor.ip), "auth.demo_login", "user", user.id)
    tokens = await start_session(session, user, actor)
    logger.info("demo session started", extra={"user_id": str(user.id)})
    return user, tokens


async def purge_ended(session: AsyncSession, storage: Storage) -> int:
    """Delete demo accounts whose session has ended, with their trees and files."""
    now = utcnow()
    live = (
        select(RefreshToken.user_id)
        .where(RefreshToken.session_expires_at > now, RefreshToken.revoked_at.is_(None))
        .scalar_subquery()
    )
    # Accounts just being created (no session yet) get a minute.
    users = list(
        await session.scalars(
            select(User).where(
                User.is_sandbox.is_(True),
                User.id.not_in(live),
                User.created_at < now - timedelta(minutes=1),
            )
        )
    )
    for user in users:
        trees = list(await session.scalars(select(Tree.id).where(Tree.owner_id == user.id)))
        for tree_id in trees:
            for prefix in _TREE_PREFIXES:
                await storage.delete_prefix(f"{prefix}/{tree_id}/")
        if trees:
            await session.execute(delete(AuditLog).where(AuditLog.tree_id.in_(trees)))
            await session.execute(delete(Tree).where(Tree.id.in_(trees)))
        await session.execute(delete(AuditLog).where(AuditLog.user_id == user.id))
        await session.delete(user)
        await session.commit()
    return len(users)
