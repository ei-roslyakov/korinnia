"""Sources and citations."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import ActorDep, PageParams, SessionDep, TreeEditor, TreeViewer
from app.models import CitedEntity
from app.schemas.common import Page
from app.schemas.sources import (
    CitationCreate,
    CitationOut,
    CitationUpdate,
    SourceCreate,
    SourceOut,
    SourceUpdate,
)
from app.services.genealogy import sources as svc

router = APIRouter(prefix="/trees/{tree_id}", tags=["sources"])


@router.get("/sources", response_model=Page[SourceOut])
async def list_sources(
    access: TreeViewer,
    session: SessionDep,
    page: PageParams,
    q: Annotated[str | None, Query(max_length=200)] = None,
) -> Page[SourceOut]:
    rows, total = await svc.search_sources(
        session, access.tree.id, q, limit=page.limit, offset=page.offset
    )
    return Page(
        items=await svc.sources_out(session, rows),
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.post("/sources", response_model=SourceOut, status_code=status.HTTP_201_CREATED)
async def create_source(
    body: SourceCreate, access: TreeEditor, session: SessionDep, actor: ActorDep
) -> SourceOut:
    source = await svc.create_source(session, access.tree.id, body, actor)
    return (await svc.sources_out(session, [source]))[0]


@router.get("/sources/{source_id}", response_model=SourceOut)
async def get_source(source_id: uuid.UUID, access: TreeViewer, session: SessionDep) -> SourceOut:
    return (
        await svc.sources_out(session, [await svc.get_source(session, access.tree.id, source_id)])
    )[0]


@router.patch("/sources/{source_id}", response_model=SourceOut)
async def update_source(
    source_id: uuid.UUID,
    body: SourceUpdate,
    access: TreeEditor,
    session: SessionDep,
    actor: ActorDep,
) -> SourceOut:
    source = await svc.get_source(session, access.tree.id, source_id)
    return (
        await svc.sources_out(session, [await svc.update_source(session, source, body, actor)])
    )[0]


@router.delete("/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(
    source_id: uuid.UUID, access: TreeEditor, session: SessionDep, actor: ActorDep
) -> None:
    """Moves the source and all its citations to the trash."""
    await svc.delete_source(
        session, await svc.get_source(session, access.tree.id, source_id), actor
    )


@router.get("/citations", response_model=list[CitationOut])
async def list_citations(
    access: TreeViewer,
    session: SessionDep,
    entity_type: CitedEntity | None = None,
    entity_id: uuid.UUID | None = None,
    source_id: uuid.UUID | None = None,
) -> list[CitationOut]:
    rows = await svc.list_citations(
        session, access.tree.id, entity_type=entity_type, entity_id=entity_id, source_id=source_id
    )
    return await svc.citations_out(session, access.tree.id, rows)


@router.post("/citations", response_model=CitationOut, status_code=status.HTTP_201_CREATED)
async def create_citation(
    body: CitationCreate, access: TreeEditor, session: SessionDep, actor: ActorDep
) -> CitationOut:
    """Attach a source to a fact (person / name / event / relationship / media)."""
    c = await svc.create_citation(session, access.tree.id, body, actor)
    return (await svc.citations_out(session, access.tree.id, [c]))[0]


@router.patch("/citations/{citation_id}", response_model=CitationOut)
async def update_citation(
    citation_id: uuid.UUID,
    body: CitationUpdate,
    access: TreeEditor,
    session: SessionDep,
    actor: ActorDep,
) -> CitationOut:
    c = await svc.get_citation(session, access.tree.id, citation_id)
    c = await svc.update_citation(session, c, body, actor)
    return (await svc.citations_out(session, access.tree.id, [c]))[0]


@router.delete("/citations/{citation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_citation(
    citation_id: uuid.UUID, access: TreeEditor, session: SessionDep, actor: ActorDep
) -> None:
    await svc.delete_citation(
        session, await svc.get_citation(session, access.tree.id, citation_id), actor
    )
