"""Assemble the full person page (details + sources + stories + research questions)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Person, TreeRole, User
from app.schemas.person_page import PersonPage
from app.services.genealogy import collaboration, sources, stories
from app.services.genealogy.persons import person_detail


async def person_page(
    session: AsyncSession, person: Person, user: User, role: TreeRole
) -> PersonPage:
    detail = await person_detail(session, person)
    visible, _ = await stories.list_stories(
        session, person.tree_id, user, role, person_id=person.id, limit=1000
    )
    return PersonPage(
        **detail.model_dump(),
        citations=await sources.citations_out(
            session, person.tree_id, await sources.person_citations(session, person)
        ),
        stories=await stories.summaries(session, visible),
        open_questions=await collaboration.questions_out(
            session,
            await collaboration.list_questions(session, person.tree_id, person_id=person.id),
        ),
    )
