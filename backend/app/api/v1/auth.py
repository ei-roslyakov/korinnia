"""Authentication endpoints: login (+2FA), refresh, logout, profile, invitations, resets."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Cookie, Request, Response, status

from app.api.cookies import (
    CSRF_COOKIE,
    MFA_COOKIE,
    REFRESH_COOKIE,
    clear_auth_cookies,
    set_mfa_cookie,
    set_session_cookies,
)
from app.api.deps import ActorDep, AnonymousActor, CurrentUser, SessionDep
from app.models import User
from app.schemas.auth import (
    AcceptInvitationRequest,
    ChangePasswordRequest,
    CsrfResponse,
    InvitationInfo,
    LoginRequest,
    LoginResponse,
    Me,
    MeTree,
    MfaRequest,
    PasswordResetInfo,
    PasswordResetRequest,
    RecoveryCodesResponse,
    TotpDisableRequest,
    TotpEnableRequest,
    TotpSetupResponse,
    UpdateMeRequest,
)
from app.services import audit
from app.services import auth as auth_service
from app.services import trees as tree_service
from app.services import users as user_service
from app.services.users import USER_AUDIT_FIELDS

router = APIRouter(prefix="/auth", tags=["auth"])


async def build_me(session: SessionDep, user: User) -> Me:
    trees = await tree_service.list_trees_for_user(session, user)
    return Me(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        preferred_language=user.preferred_language,
        is_superadmin=user.is_superadmin,
        totp_enabled=user.totp_enabled,
        trees=[MeTree(id=t.id, name=t.name, role=role) for t, role in trees],
    )


@router.get("/csrf", response_model=CsrfResponse)
async def csrf(request: Request) -> CsrfResponse:
    """Return the CSRF token. CSRFMiddleware sets the cookie when it is missing."""
    token = request.cookies.get(CSRF_COOKIE) or request.state.csrf_token
    return CsrfResponse(csrf_token=token)


@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest, response: Response, session: SessionDep, actor: AnonymousActor
) -> LoginResponse:
    user = await auth_service.authenticate(session, body.email, body.password, actor)
    if user.totp_enabled:
        await session.commit()  # persist a possible password rehash
        set_mfa_cookie(response, auth_service.create_mfa_token(user))
        return LoginResponse(status="mfa_required")
    tokens = await auth_service.start_session(session, user, actor)
    set_session_cookies(response, access=tokens.access, refresh=tokens.refresh)
    return LoginResponse(status="ok", user=await build_me(session, user))


@router.post("/login/mfa", response_model=LoginResponse)
async def login_mfa(
    body: MfaRequest,
    response: Response,
    session: SessionDep,
    actor: AnonymousActor,
    mfa_token: Annotated[str | None, Cookie(alias=MFA_COOKIE)] = None,
) -> LoginResponse:
    user = await auth_service.complete_mfa(session, mfa_token, body.code, actor)
    tokens = await auth_service.start_session(session, user, actor)
    set_session_cookies(response, access=tokens.access, refresh=tokens.refresh)
    return LoginResponse(status="ok", user=await build_me(session, user))


@router.post("/refresh", status_code=status.HTTP_204_NO_CONTENT)
async def refresh(
    response: Response,
    session: SessionDep,
    actor: AnonymousActor,
    refresh_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE)] = None,
) -> None:
    try:
        _, tokens = await auth_service.refresh_session(session, refresh_token, actor)
    except Exception:
        clear_auth_cookies(response)
        raise
    set_session_cookies(response, access=tokens.access, refresh=tokens.refresh)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    session: SessionDep,
    refresh_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE)] = None,
) -> None:
    await auth_service.logout(session, refresh_token)
    clear_auth_cookies(response)


@router.get("/me", response_model=Me)
async def me(user: CurrentUser, session: SessionDep) -> Me:
    return await build_me(session, user)


@router.patch("/me", response_model=Me)
async def update_me(body: UpdateMeRequest, session: SessionDep, actor: ActorDep) -> Me:
    user = actor.user
    assert user is not None
    before = audit.snapshot(user, USER_AUDIT_FIELDS)
    if body.display_name is not None:
        user.display_name = body.display_name.strip()
    if body.preferred_language is not None:
        user.preferred_language = body.preferred_language
    after = audit.snapshot(user, USER_AUDIT_FIELDS)
    if before != after:
        b, a = audit.diff_only(before, after)
        audit.record(session, actor, "user.update", "user", user.id, before=b, after=a)
    await session.commit()
    return await build_me(session, user)


@router.post("/me/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    body: ChangePasswordRequest, response: Response, session: SessionDep, actor: ActorDep
) -> None:
    assert actor.user is not None
    tokens = await auth_service.change_password(
        session, actor.user, body.current_password, body.new_password, actor
    )
    set_session_cookies(response, access=tokens.access, refresh=tokens.refresh)


# --- 2FA --------------------------------------------------------------------------------


@router.post("/2fa/setup", response_model=TotpSetupResponse)
async def totp_setup(user: CurrentUser, session: SessionDep) -> TotpSetupResponse:
    secret, uri, svg = await auth_service.totp_setup(session, user)
    return TotpSetupResponse(secret=secret, otpauth_uri=uri, qr_svg=svg)


@router.post("/2fa/enable", response_model=RecoveryCodesResponse)
async def totp_enable(
    body: TotpEnableRequest, session: SessionDep, actor: ActorDep
) -> RecoveryCodesResponse:
    assert actor.user is not None
    codes = await auth_service.totp_enable(session, actor.user, body.code, actor)
    return RecoveryCodesResponse(recovery_codes=codes)


@router.post("/2fa/disable", status_code=status.HTTP_204_NO_CONTENT)
async def totp_disable(body: TotpDisableRequest, session: SessionDep, actor: ActorDep) -> None:
    assert actor.user is not None
    await auth_service.totp_disable(session, actor.user, body.password, body.code, actor)


@router.post("/2fa/recovery-codes", response_model=RecoveryCodesResponse)
async def regenerate_recovery_codes(
    body: MfaRequest, session: SessionDep, actor: ActorDep
) -> RecoveryCodesResponse:
    assert actor.user is not None
    codes = await auth_service.regenerate_recovery_codes(session, actor.user, body.code, actor)
    return RecoveryCodesResponse(recovery_codes=codes)


# --- Invitations & password reset (public, token-based) ---------------------------------


@router.get("/invitations/{token}", response_model=InvitationInfo)
async def invitation_info(token: str, session: SessionDep) -> InvitationInfo:
    inv = await user_service.get_valid_invitation(session, token)
    return InvitationInfo(
        email=inv.email,
        tree_name=inv.tree.name if inv.tree else None,
        role=inv.role,
        is_superadmin=inv.is_superadmin,
        expires_at=inv.expires_at,
    )


@router.post("/invitations/{token}/accept", response_model=LoginResponse)
async def accept_invitation(
    token: str,
    body: AcceptInvitationRequest,
    response: Response,
    session: SessionDep,
    actor: AnonymousActor,
) -> LoginResponse:
    user = await user_service.accept_invitation(
        session,
        token,
        display_name=body.display_name,
        password=body.password,
        preferred_language=body.preferred_language,
        actor=actor,
    )
    tokens = await auth_service.start_session(session, user, actor)
    set_session_cookies(response, access=tokens.access, refresh=tokens.refresh)
    return LoginResponse(status="ok", user=await build_me(session, user))


@router.get("/password-reset/{token}", response_model=PasswordResetInfo)
async def password_reset_info(token: str, session: SessionDep) -> PasswordResetInfo:
    row = await user_service.get_password_reset(session, token)
    return PasswordResetInfo(email=row.user.email, expires_at=row.expires_at)


@router.post("/password-reset/{token}", status_code=status.HTTP_204_NO_CONTENT)
async def password_reset(
    token: str, body: PasswordResetRequest, session: SessionDep, actor: AnonymousActor
) -> None:
    await user_service.consume_password_reset(session, token, body.password, actor)
