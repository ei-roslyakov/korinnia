"""Application errors with stable machine-readable codes (the frontend translates codes)."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    status_code = 400

    def __init__(
        self,
        code: str,
        message: str | None = None,
        *,
        status_code: int | None = None,
        headers: dict[str, str] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message or code)
        self.code = code
        self.message = message or code.replace("_", " ")
        if status_code is not None:
            self.status_code = status_code
        self.headers = headers
        self.extra = extra or {}


class NotAuthenticatedError(AppError):
    status_code = 401

    def __init__(self, code: str = "not_authenticated") -> None:
        super().__init__(code)


class PermissionDeniedError(AppError):
    status_code = 403

    def __init__(self, code: str = "permission_denied") -> None:
        super().__init__(code)


class NotFoundError(AppError):
    status_code = 404

    def __init__(self, code: str = "not_found") -> None:
        super().__init__(code)


class ConflictError(AppError):
    status_code = 409


class TooManyRequestsError(AppError):
    status_code = 429

    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__(
            "too_many_attempts",
            headers={"Retry-After": str(retry_after_seconds)},
            extra={"retry_after": retry_after_seconds},
        )


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message, "code": exc.code, **exc.extra},
            headers=exc.headers,
        )
