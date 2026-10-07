from __future__ import annotations

from app.schemas.collaboration import QuestionOut
from app.schemas.persons import PersonDetail
from app.schemas.sources import CitationOut
from app.schemas.stories import StorySummary


class PersonPage(PersonDetail):
    """Everything shown on a person's page: details plus sources, stories, questions."""

    citations: list[CitationOut]
    stories: list[StorySummary]
    open_questions: list[QuestionOut]
