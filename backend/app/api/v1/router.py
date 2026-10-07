"""REST API v1 — all feature routers are mounted here."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.v1 import admin, auth, events, history, persons, places, relationships, trees
from app.core.config import Settings, get_settings

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(trees.router)
api_router.include_router(admin.router)
for genealogy in (persons, places, events, relationships, history):
    api_router.include_router(genealogy.router)


class MetaInfo(BaseModel):
    name: str
    version: str
    environment: str


@api_router.get("/meta", response_model=MetaInfo, tags=["meta"])
async def meta(settings: Annotated[Settings, Depends(get_settings)]) -> MetaInfo:
    """Basic, non-sensitive information about this installation."""
    return MetaInfo(
        name="Korinnia",
        version=settings.app_version,
        environment=settings.environment,
    )
