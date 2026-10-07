"""CSRF protection (double-submit cookie), as a pure ASGI middleware.

Every response to a request without a CSRF cookie sets one. State-changing requests
(POST/PUT/PATCH/DELETE) to /api/ must echo the cookie value in the X-CSRF-Token header.
Combined with SameSite=Lax auth cookies this blocks cross-site request forgery, including
login CSRF. Pure ASGI (not BaseHTTPMiddleware) so large upload bodies stream untouched.
"""

from __future__ import annotations

import json
from http.cookies import SimpleCookie

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.api.cookies import CSRF_COOKIE, CSRF_HEADER, csrf_cookie_header
from app.core.security import generate_csrf_token, tokens_equal

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})


def _cookie_value(scope: Scope, name: str) -> str | None:
    for key, value in scope.get("headers", []):
        if key == b"cookie":
            cookie = SimpleCookie()
            try:
                cookie.load(value.decode("latin-1"))
            except Exception:  # malformed cookie header
                return None
            if name in cookie:
                return cookie[name].value
    return None


def _header_value(scope: Scope, name: str) -> str | None:
    target = name.encode()
    for key, value in scope.get("headers", []):
        if key.lower() == target:
            return str(value.decode("latin-1"))
    return None


class CSRFMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        cookie_token = _cookie_value(scope, CSRF_COOKIE)
        path: str = scope.get("path", "")
        if scope["method"] not in SAFE_METHODS and path.startswith("/api/"):
            header_token = _header_value(scope, CSRF_HEADER)
            if not cookie_token or not header_token or not tokens_equal(cookie_token, header_token):
                await self._reject(send)
                return

        if cookie_token:
            await self.app(scope, receive, send)
            return

        new_token = generate_csrf_token()
        # Exposed to endpoints as request.state.csrf_token (see GET /auth/csrf).
        scope.setdefault("state", {})["csrf_token"] = new_token

        async def send_with_cookie(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"set-cookie", csrf_cookie_header(new_token).encode("latin-1")))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_cookie)

    @staticmethod
    async def _reject(send: Send) -> None:
        body = json.dumps({"detail": "CSRF token missing or invalid", "code": "csrf_failed"})
        await send(
            {
                "type": "http.response.start",
                "status": 403,
                "headers": [(b"content-type", b"application/json")],
            }
        )
        await send({"type": "http.response.body", "body": body.encode()})
