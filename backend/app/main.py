"""FastAPI application entrypoint."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.csrf import CSRFMiddleware
from app.api.health import router as health_router
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.db import get_engine
from app.core.errors import install_error_handlers
from app.core.logging import configure_logging


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    await get_engine().dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    docs_enabled = not settings.is_production
    app = FastAPI(
        title="Korinnia API",
        version=settings.app_version,
        lifespan=lifespan,
        docs_url="/api/docs" if docs_enabled else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if docs_enabled else None,
    )
    # Probes are reachable both directly (container healthcheck) and through nginx (/api/...).
    app.include_router(health_router)
    app.include_router(health_router, prefix="/api", include_in_schema=False)
    app.include_router(api_router, prefix="/api/v1")
    install_error_handlers(app)
    app.add_middleware(CSRFMiddleware)
    return app


app = create_app()
