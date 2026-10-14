"""Authentication: passwords, sessions (access/refresh JWTs), throttling, TOTP 2FA."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import (
    AppError,
    ConflictError,
    NotAuthenticatedError,
    PermissionDeniedError,
    TooManyRequestsError,
)
from app.core.security import (
    TokenError,
    create_token,
    decode_token,
    decrypt_secret,
    encrypt_secret,
    generate_recovery_codes,
    generate_totp_secret,
    hash_password,
    hash_token,
    normalize_recovery_code,
    password_needs_rehash,
    totp_provisioning_uri,
    totp_qr_svg,
    utcnow,
    verify_password,
    verify_totp,
)
from app.models import LoginAttempt, RecoveryCode, RefreshToken, User
from app.services import audit
from app.services.context import Actor

# A refresh token replaced less than this long ago may be presented again without being
# treated as theft: parallel tabs / requests commonly race to refresh at the same moment.
REFRESH_REUSE_GRACE = timedelta(seconds=30)


@dataclass(frozen=True, slots=True)
class SessionTokens:
    access: str
    refresh: str
    session_expires_at: datetime


def _now_s() -> datetime:
    """Current time truncated to seconds (JWT `iat` precision)."""
    return utcnow().replace(microsecond=0)


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    result = await session.scalars(
        select(User).where(func.lower(User.email) == email.strip().lower())
    )
    return result.first()


def session_revoked(user: User, issued_at: datetime) -> bool:
    """True if a token issued at `issued_at` predates the user's session cut-off.

    JWT `iat` has second precision, so the cut-off is compared at second precision too.
    """
    return issued_at < user.sessions_valid_after.replace(microsecond=0)


# --- Throttling -------------------------------------------------------------------------


async def _failures_since(
    session: AsyncSession, column: object, value: str, since: datetime
) -> tuple[int, datetime | None]:
    row = (
        await session.execute(
            select(func.count(), func.min(LoginAttempt.created_at)).where(
                column == value,  # type: ignore[arg-type]
                LoginAttempt.success.is_(False),
                LoginAttempt.created_at >= since,
            )
        )
    ).one()
    return int(row[0]), row[1]


async def check_throttle(session: AsyncSession, email: str, ip: str | None) -> None:
    s = get_settings()
    window = timedelta(minutes=s.login_window_minutes)
    now = utcnow()
    since = now - window
    checks: list[tuple[object, str, int]] = [
        (LoginAttempt.email, email, s.login_max_failures_per_email)
    ]
    if ip:
        checks.append((LoginAttempt.ip_address, ip, s.login_max_failures_per_ip))
    for column, value, limit in checks:
        count, oldest = await _failures_since(session, column, value, since)
        if count >= limit:
            retry = int(((oldest or now) + window - now).total_seconds()) + 1
            raise TooManyRequestsError(max(retry, 1))


async def record_attempt(
    session: AsyncSession, email: str, ip: str | None, *, success: bool
) -> None:
    session.add(LoginAttempt(email=email, ip_address=ip, success=success))


async def _fail_login(session: AsyncSession, email: str, actor: Actor, code: str) -> AppError:
    """Persist the failed attempt (even though the request fails) and build the error."""
    await record_attempt(session, email, actor.ip, success=False)
    await session.commit()
    return AppError(code, status_code=401)


# --- Password login ---------------------------------------------------------------------


async def authenticate(session: AsyncSession, email: str, password: str, actor: Actor) -> User:
    email = email.strip().lower()
    await check_throttle(session, email, actor.ip)
    user = await get_user_by_email(session, email)
    if not verify_password(password, user.password_hash if user else None) or user is None:
        raise await _fail_login(session, email, actor, "invalid_credentials")
    if not user.is_active:
        raise await _fail_login(session, email, actor, "account_disabled")
    if user.password_hash and password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    return user


def create_mfa_token(user: User) -> str:
    ttl = timedelta(minutes=get_settings().mfa_token_ttl_minutes)
    return create_token(user.id, "mfa", ttl)


async def complete_mfa(
    session: AsyncSession, mfa_token: str | None, code: str, actor: Actor
) -> User:
    if not mfa_token:
        raise NotAuthenticatedError("mfa_session_expired")
    try:
        payload = decode_token(mfa_token, "mfa")
    except TokenError as exc:
        raise NotAuthenticatedError("mfa_session_expired") from exc
    user = await session.get(User, payload.sub)
    if user is None or not user.is_active or not user.totp_enabled:
        raise NotAuthenticatedError("mfa_session_expired")
    await check_throttle(session, user.email.lower(), actor.ip)
    if not await verify_second_factor(session, user, code):
        raise await _fail_login(session, user.email.lower(), actor, "invalid_code")
    return user


async def verify_second_factor(session: AsyncSession, user: User, code: str) -> bool:
    """Accept a current TOTP code or an unused recovery code (which is then consumed)."""
    if user.totp_secret:
        secret = decrypt_secret(user.totp_secret)
        counter = verify_totp(secret, code, last_counter=user.totp_last_counter)
        if counter is not None:
            user.totp_last_counter = counter
            return True
    code_hash = hash_token(normalize_recovery_code(code))
    recovery = (
        await session.scalars(
            select(RecoveryCode).where(
                RecoveryCode.user_id == user.id,
                RecoveryCode.code_hash == code_hash,
                RecoveryCode.used_at.is_(None),
            )
        )
    ).first()
    if recovery is not None:
        recovery.used_at = utcnow()
        return True
    return False


# --- Sessions ---------------------------------------------------------------------------


def session_timeout(user: User) -> timedelta:
    s = get_settings()
    minutes = s.demo_session_timeout_minutes if user.is_sandbox else s.session_timeout_minutes
    return timedelta(minutes=minutes)


def _new_refresh_row(
    user: User, family_id: uuid.UUID, actor: Actor, session_expires_at: datetime | None = None
) -> RefreshToken:
    now = _now_s()
    return RefreshToken(
        id=uuid.uuid4(),
        user_id=user.id,
        family_id=family_id,
        expires_at=now + timedelta(days=get_settings().refresh_token_ttl_days),
        session_expires_at=session_expires_at or now + session_timeout(user),
        user_agent=(actor.user_agent or "")[:500] or None,
        ip_address=actor.ip,
    )


def _tokens_for(user: User, row: RefreshToken) -> SessionTokens:
    s = get_settings()
    end = row.session_expires_at
    assert end is not None
    return SessionTokens(
        access=create_token(
            user.id,
            "access",
            timedelta(minutes=s.access_token_ttl_minutes),
            session_expires_at=end,
        ),
        refresh=create_token(
            user.id,
            "refresh",
            timedelta(days=s.refresh_token_ttl_days),
            jti=row.id,
            family_id=row.family_id,
            session_expires_at=end,
        ),
        session_expires_at=end,
    )


async def start_session(session: AsyncSession, user: User, actor: Actor) -> SessionTokens:
    """Called after successful authentication (password and, if enabled, 2FA). The session
    ends after `session_timeout`; the user can extend it before then (`refresh_session`)."""
    row = _new_refresh_row(user, uuid.uuid4(), actor)
    session.add(row)
    user.last_login_at = utcnow()
    await record_attempt(session, user.email.lower(), actor.ip, success=True)
    audit.record(session, Actor(user, actor.ip), "auth.login", "user", user.id)
    await session.commit()
    return _tokens_for(user, row)


async def refresh_session(
    session: AsyncSession, refresh_token: str | None, actor: Actor, *, extend: bool = False
) -> tuple[User, SessionTokens]:
    """Rotate the refresh token. The session keeps its end time; `extend` moves it to a full
    timeout from now (not for demo accounts). An ended session cannot be refreshed."""
    if not refresh_token:
        raise NotAuthenticatedError()
    try:
        payload = decode_token(refresh_token, "refresh")
    except TokenError as exc:
        raise NotAuthenticatedError(exc.code) from exc
    row = await session.get(RefreshToken, payload.jti) if payload.jti else None
    if row is None or row.user_id != payload.sub:
        raise NotAuthenticatedError("token_invalid")
    now = utcnow()
    if row.revoked_at is not None:
        if (
            row.replaced_by_id is not None
            and now - row.revoked_at <= REFRESH_REUSE_GRACE
            and await _family_is_live(session, row.family_id)
        ):
            pass  # benign race between parallel refreshes: issue another token below
        else:
            if row.replaced_by_id is not None:
                # A rotated-out token was replayed: assume theft, end the whole session.
                await revoke_family(session, row.family_id)
                await session.commit()
            raise NotAuthenticatedError("token_revoked")
    if row.expires_at <= now:
        raise NotAuthenticatedError("token_expired")
    user = await session.get(User, row.user_id)
    if user is None or not user.is_active or session_revoked(user, payload.iat):
        raise NotAuthenticatedError("token_revoked")
    # Sessions started before timeouts existed get one now.
    end = row.session_expires_at or _now_s() + session_timeout(user)
    if end <= now:
        raise NotAuthenticatedError("session_expired")
    if extend:
        if user.is_sandbox:
            raise PermissionDeniedError("demo_session_fixed")
        end = _now_s() + session_timeout(user)
        audit.record(session, Actor(user, actor.ip), "auth.session_extend", "user", user.id)

    new_row = _new_refresh_row(user, row.family_id, actor, end)
    session.add(new_row)
    if row.revoked_at is None:
        row.revoked_at = now
        row.replaced_by_id = new_row.id
    await session.commit()
    return user, _tokens_for(user, new_row)


async def _family_is_live(session: AsyncSession, family_id: uuid.UUID) -> bool:
    """True if the session (family) still has an unrevoked token, i.e. was not logged out."""
    live = await session.scalar(
        select(func.count()).where(
            RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None)
        )
    )
    return bool(live)


async def revoke_family(session: AsyncSession, family_id: uuid.UUID) -> None:
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )


async def logout(session: AsyncSession, refresh_token: str | None) -> None:
    if not refresh_token:
        return
    try:
        payload = decode_token(refresh_token, "refresh")
    except TokenError:
        return
    if payload.fam:
        await revoke_family(session, payload.fam)
        await session.commit()


async def revoke_all_sessions(session: AsyncSession, user: User) -> None:
    """Invalidate every access and refresh token issued to the user so far."""
    user.sessions_valid_after = _now_s()
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )


# --- Password change --------------------------------------------------------------------


async def change_password(
    session: AsyncSession, user: User, current: str, new: str, actor: Actor
) -> SessionTokens:
    if not verify_password(current, user.password_hash):
        raise AppError("invalid_password", status_code=400)
    user.password_hash = hash_password(new)
    await revoke_all_sessions(session, user)
    audit.record(session, actor, "user.password_change", "user", user.id)
    # Keep the current browser logged in with a fresh session.
    row = _new_refresh_row(user, uuid.uuid4(), actor)
    session.add(row)
    await session.commit()
    return _tokens_for(user, row)


# --- TOTP setup -------------------------------------------------------------------------


async def totp_setup(session: AsyncSession, user: User) -> tuple[str, str, str]:
    if user.totp_enabled:
        raise ConflictError("totp_already_enabled")
    secret = generate_totp_secret()
    user.totp_secret = encrypt_secret(secret)
    user.totp_last_counter = None
    await session.commit()
    uri = totp_provisioning_uri(secret, user.email)
    return secret, uri, totp_qr_svg(uri)


async def _replace_recovery_codes(session: AsyncSession, user: User) -> list[str]:
    await session.execute(delete(RecoveryCode).where(RecoveryCode.user_id == user.id))
    codes = generate_recovery_codes()
    session.add_all(RecoveryCode(user_id=user.id, code_hash=hash_token(c)) for c in codes)
    return codes


async def totp_enable(session: AsyncSession, user: User, code: str, actor: Actor) -> list[str]:
    if user.totp_enabled:
        raise ConflictError("totp_already_enabled")
    if not user.totp_secret:
        raise AppError("totp_not_set_up")
    counter = verify_totp(decrypt_secret(user.totp_secret), code, last_counter=None)
    if counter is None:
        raise AppError("invalid_code")
    user.totp_enabled = True
    user.totp_last_counter = counter
    codes = await _replace_recovery_codes(session, user)
    audit.record(session, actor, "user.2fa_enable", "user", user.id)
    await session.commit()
    return codes


async def totp_disable(
    session: AsyncSession, user: User, password: str, code: str, actor: Actor
) -> None:
    if not user.totp_enabled:
        raise AppError("totp_not_enabled")
    if not verify_password(password, user.password_hash):
        raise AppError("invalid_password")
    if not await verify_second_factor(session, user, code):
        raise AppError("invalid_code")
    await clear_totp(session, user)
    audit.record(session, actor, "user.2fa_disable", "user", user.id)
    await session.commit()


async def regenerate_recovery_codes(
    session: AsyncSession, user: User, code: str, actor: Actor
) -> list[str]:
    if not user.totp_enabled:
        raise AppError("totp_not_enabled")
    if not await verify_second_factor(session, user, code):
        raise AppError("invalid_code")
    codes = await _replace_recovery_codes(session, user)
    audit.record(session, actor, "user.2fa_recovery_codes", "user", user.id)
    await session.commit()
    return codes


async def clear_totp(session: AsyncSession, user: User) -> None:
    user.totp_enabled = False
    user.totp_secret = None
    user.totp_last_counter = None
    await session.execute(delete(RecoveryCode).where(RecoveryCode.user_id == user.id))


# --- Maintenance ------------------------------------------------------------------------


async def purge_expired(session: AsyncSession) -> tuple[int, int]:
    """Delete old login attempts and long-expired refresh tokens."""
    now = utcnow()
    attempts = await session.execute(
        delete(LoginAttempt).where(LoginAttempt.created_at < now - timedelta(days=30))
    )
    tokens = await session.execute(
        delete(RefreshToken).where(RefreshToken.expires_at < now - timedelta(days=7))
    )
    await session.commit()
    return attempts.rowcount or 0, tokens.rowcount or 0  # type: ignore[attr-defined]
