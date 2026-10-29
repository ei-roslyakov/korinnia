"""Exports of a tree: GEDCOM 5.5.1 (more formats come with the family archive, phase 11)."""

from __future__ import annotations

import re
from datetime import date
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Query, Response

from app.api.deps import ActorDep, SessionDep, TreeViewer, VisibilityDep
from app.core.config import get_settings
from app.exporters.gedcom import export_tree
from app.services import audit
from app.services.search_text import transliterate_uk

router = APIRouter(prefix="/trees/{tree_id}/export", tags=["exports"])


def _file_name(tree_name: str) -> str:
    base = re.sub(r'[\\/:*?"<>|]+', "", tree_name).strip()
    base = re.sub(r"\s+", "-", base)[:80] or "tree"
    return f"{base}-{date.today().isoformat()}.ged"


@router.get("/gedcom", response_class=Response)
async def export_gedcom(
    access: TreeViewer,
    session: SessionDep,
    actor: ActorDep,
    seen: VisibilityDep,
    living: Annotated[bool, Query(description="False: living people only as 'Living'")] = True,
) -> Response:
    """The tree as a GEDCOM 5.5.1 file (UTF-8). With `living=false` living people keep their
    place in the family but appear as "Living <surname>", without dates, notes or sources.
    Readers who see only the basics of living people always get that version."""
    tree = access.tree
    living = living and not seen.restricted
    text = await export_tree(
        session,
        tree,
        hide_living=not living,
        app_version=get_settings().app_version,
        submitter=actor.user.display_name if actor.user else None,
    )
    audit.record(
        session,
        actor,
        "tree.export",
        "tree",
        tree.id,
        tree_id=tree.id,
        after={"format": "gedcom", "living": living},
    )
    await session.commit()
    name = _file_name(tree.name)
    # Browsers without RFC 5987 support get a transliterated name ("rodyna-kovalenkiv-…").
    ascii_name = transliterate_uk(name).encode("ascii", "ignore").decode() or "tree.ged"
    return Response(
        content=text.encode("utf-8"),
        media_type="application/x-gedcom; charset=utf-8",
        headers={
            "Content-Disposition": (
                f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(name)}"
            ),
            "Cache-Control": "no-store",
        },
    )
