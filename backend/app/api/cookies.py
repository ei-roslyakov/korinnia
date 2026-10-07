"""Auth cookie names, paths and helpers.

- access:  httpOnly, sent to all /api requests, short-lived
- refresh: httpOnly, only sent to /api/v1/auth (refresh/logout), long-lived
- mfa:     httpOnly, only /api/v1/auth, minutes — proves the password step of a 2FA login
- csrf:    readable by JS (double-submit pattern), echoed in the X-CSRF-Token header
"""

from __future__ import annotations

from datetime import timedelta

from fastapi import Response

from app.core.config import get_settings

ACCESS_COOKIE = "korinnia_access"
REFRESH_COOKIE = "korinnia_refresh"
MFA_COOKIE = "korinnia_mfa"
CSRF_COOKIE = "korinnia_csrf"
CSRF_HEADER = "x-csrf-token"

ACCESS_PATH = "/api"
AUTH_PATH = "/api/v1/auth"


def _set(response: Response, name: str, value: str, *, path: str, max_age: timedelta) -> None:
    response.set_cookie(
        name,
        value,
        max_age=int(max_age.total_seconds()),
        path=path,
        secure=get_settings().cookie_secure,
        httponly=True,
        samesite="lax",
    )


def set_session_cookies(response: Response, *, access: str, refresh: str) -> None:
    s = get_settings()
    _set(
        response,
        ACCESS_COOKIE,
        access,
        path=ACCESS_PATH,
        max_age=timedelta(minutes=s.access_token_ttl_minutes),
    )
    _set(
        response,
        REFRESH_COOKIE,
        refresh,
        path=AUTH_PATH,
        max_age=timedelta(days=s.refresh_token_ttl_days),
    )
    response.delete_cookie(MFA_COOKIE, path=AUTH_PATH)


def set_mfa_cookie(response: Response, token: str) -> None:
    _set(
        response,
        MFA_COOKIE,
        token,
        path=AUTH_PATH,
        max_age=timedelta(minutes=get_settings().mfa_token_ttl_minutes),
    )


def clear_auth_cookies(response: Response) -> None:
    secure = get_settings().cookie_secure
    for name, path in (
        (ACCESS_COOKIE, ACCESS_PATH),
        (REFRESH_COOKIE, AUTH_PATH),
        (MFA_COOKIE, AUTH_PATH),
    ):
        response.delete_cookie(name, path=path, secure=secure, httponly=True, samesite="lax")


def csrf_cookie_header(token: str) -> str:
    secure = "; Secure" if get_settings().cookie_secure else ""
    return f"{CSRF_COOKIE}={token}; Path=/; SameSite=Lax{secure}"
