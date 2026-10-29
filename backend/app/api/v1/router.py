"""REST API v1 — all feature routers are mounted here."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.v1 import (
    admin,
    auth,
    calendar,
    collaboration,
    events,
    exports,
    history,
    imports,
    insights,
    media,
    persons,
    places,
    relationships,
    share,
    sources,
    stories,
    trees,
)
from app.core.config import Settings, get_settings
from app.core.enums import Language

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(trees.router)
api_router.include_router(admin.router)
for genealogy in (
    persons,
    places,
    events,
    relationships,
    history,
    media,
    sources,
    stories,
    collaboration,
    insights,
    calendar,
    imports,
    exports,
    share,
):
    api_router.include_router(genealogy.router)


class DemoLogin(BaseModel):
    """The public demo credentials (meant to be published)."""

    email: str
    password: str


class MetaInfo(BaseModel):
    name: str
    version: str
    environment: str
    default_language: Language
    # Shown on the sign-in page when DEMO_LOGIN_ENABLED.
    demo_login: DemoLogin | None = None


@api_router.get("/meta", response_model=MetaInfo, tags=["meta"])
async def meta(settings: Annotated[Settings, Depends(get_settings)]) -> MetaInfo:
    """Basic, non-sensitive information about this installation."""
    return MetaInfo(
        name="Korinnia",
        version=settings.app_version,
        environment=settings.environment,
        default_language=settings.default_language,
        demo_login=DemoLogin(
            email=settings.demo_login_email,
            password=settings.demo_login_password.get_secret_value(),
        )
        if settings.demo_login_enabled
        else None,
    )
