"""Liveness and readiness probes (outside /api/v1: probes never depend on API version)."""

from __future__ import annotations

import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel

from app.core.db import ping_database
from app.storage import Storage, get_storage

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


class HealthStatus(BaseModel):
    status: Literal["ok", "error"]


class ReadinessStatus(BaseModel):
    status: Literal["ok", "error"]
    checks: dict[str, Literal["ok", "error"]]


@router.get("/healthz", response_model=HealthStatus)
async def healthz() -> HealthStatus:
    """Liveness: the process is up and serving requests."""
    return HealthStatus(status="ok")


@router.get("/readyz", response_model=ReadinessStatus)
async def readyz(
    response: Response, storage: Annotated[Storage, Depends(get_storage)]
) -> ReadinessStatus:
    """Readiness: database and file storage are reachable."""
    checks: dict[str, Literal["ok", "error"]] = {}
    try:
        await ping_database()
        checks["database"] = "ok"
    except Exception:
        logger.exception("readiness: database check failed")
        checks["database"] = "error"
    try:
        await storage.check()
        checks["storage"] = "ok"
    except Exception:
        logger.exception("readiness: storage check failed")
        checks["storage"] = "error"

    ok = all(v == "ok" for v in checks.values())
    if not ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessStatus(status="ok" if ok else "error", checks=checks)
