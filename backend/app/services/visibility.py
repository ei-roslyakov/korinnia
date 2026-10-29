"""What a reader may see of living people (D114).

A tree's admins choose who sees only the basics of living people (`Tree.living_privacy`):
share-link visitors (the default), also members with the viewer role, or nobody.
For such a *restricted* reader, a *protected* person (`Person.is_living`) keeps their name,
gender, place in the family and birth year; everything else is left out: exact dates,
places, events, biography and facts, photos and documents, stories only about them,
comments, research questions and the sources of their facts. The portrait stays only when
the admins allow it (`Tree.show_living_portraits`).

Every endpoint that reads a tree asks for a `Visibility` and applies it before answering,
so nothing depends on the browser hiding things.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import CitedEntity, DatePrecision, LivingPrivacy, TreeRole
from app.models import (
    Citation,
    EventParticipant,
    MediaPerson,
    ParentChild,
    Partnership,
    Person,
    PersonName,
    Tree,
)
from app.schemas.dates import PartialDateOut
from app.schemas.media import MediaOut
from app.schemas.person_page import PersonPage
from app.schemas.persons import PartnerRef, PersonSummary
from app.schemas.relationships import GraphPartnership


def restricts(tree: Tree, role: TreeRole, *, via_share_link: bool) -> bool:
    """Whether this reader sees only the basics of living people. Contributors, editors and
    admins always see everything."""
    if tree.living_privacy == LivingPrivacy.off:
        return False
    if via_share_link:
        return True
    return tree.living_privacy == LivingPrivacy.viewers_and_share_links and (
        role == TreeRole.viewer
    )


def year_only(d: PartialDateOut | None) -> PartialDateOut | None:
    """The year of a date (an approximate year stays a range, e.g. "1950s")."""
    if d is None or d.year is None:
        return None
    return PartialDateOut(
        year=d.year, month=None, day=None, precision=DatePrecision.year,
        end_year=None, end_month=None, end_day=None, phrase=None,
        text=str(d.year), sort=d.sort.replace(month=1, day=1) if d.sort else None,
    )  # fmt: skip


@dataclass(frozen=True, slots=True)
class Visibility:
    restricted: bool = False
    show_portraits: bool = False
    # Living people of the tree (only filled for restricted readers).
    protected: frozenset[uuid.UUID] = field(default_factory=frozenset)
    # Events with a protected participant; media showing a protected person or used as
    # their portrait.
    hidden_events: frozenset[uuid.UUID] = field(default_factory=frozenset)
    hidden_media: frozenset[uuid.UUID] = field(default_factory=frozenset)

    def hides_person(self, person_id: uuid.UUID | None) -> bool:
        return person_id in self.protected

    def hides_event(self, event_id: uuid.UUID) -> bool:
        return event_id in self.hidden_events

    def hides_media(self, media_id: uuid.UUID) -> bool:
        return media_id in self.hidden_media

    def hides_story(self, person_ids: Sequence[uuid.UUID]) -> bool:
        """A story is hidden when everyone it is about is protected."""
        return bool(person_ids) and all(p in self.protected for p in person_ids)

    # --- Responses ----------------------------------------------------------------------

    def summary(self, s: PersonSummary) -> PersonSummary:
        if s.id not in self.protected:
            return s
        s.details_hidden = True
        s.birth = year_only(s.birth)
        s.death = None
        s.birth_place = None
        s.primary_photo_id = None
        if not (self.show_portraits and s.avatar_url and "/avatar" in s.avatar_url):
            s.avatar_url = None
        return s

    def redact[T](self, obj: T) -> T:
        """Redact, in place, every person summary, partnership and media list in a response.
        A no-op for readers who see everything."""
        if self.restricted:
            self._walk(obj)
        return obj

    def _walk(self, obj: Any) -> None:
        if isinstance(obj, PersonSummary):
            self.summary(obj)
            return
        if isinstance(obj, GraphPartnership) and (
            obj.person_a_id in self.protected or obj.person_b_id in self.protected
        ):
            obj.start_date, obj.end_date, obj.place = None, None, None
        if isinstance(obj, PartnerRef) and obj.person.id in self.protected:
            obj.start_date, obj.end_date = None, None
        if isinstance(obj, BaseModel):
            for name in type(obj).model_fields:
                value = getattr(obj, name)
                if isinstance(value, list) and value and isinstance(value[0], MediaOut):
                    setattr(obj, name, [m for m in value if m.id not in self.hidden_media])
                else:
                    self._walk(value)
        elif isinstance(obj, list | tuple):
            for item in obj:
                self._walk(item)
        elif isinstance(obj, dict):
            for item in obj.values():
                self._walk(item)

    def person_page(self, page: PersonPage) -> PersonPage:
        if not self.restricted:
            return page
        if page.id in self.protected:
            primary = next((n for n in page.names if n.is_primary), None) or (
                page.names[0] if page.names else None
            )
            page.details_hidden = True
            page.names = [primary.model_copy(update={"notes": None})] if primary else []
            for f in (
                "short_summary", "biography", "occupation", "education", "religion",
                "nationality", "notes_for_descendants", "primary_photo_id", "primary_photo_crop",
            ):  # fmt: skip
                setattr(page, f, None)
            if not (self.show_portraits and page.avatar_url and "/avatar" in page.avatar_url):
                page.avatar_url = None
            page.portrait_pending = False
            if page.birth is not None:
                page.birth = page.birth.model_copy(
                    update={"date": year_only(page.birth.date), "place": None, "description": None}
                )
            page.death = None
            page.events, page.media, page.warnings = [], [], []
            page.citations, page.open_questions = [], []
        else:
            page.events = [e for e in page.events if e.id not in self.hidden_events]
        page.stories = [s for s in page.stories if not self.hides_story(s.person_ids)]
        return self.redact(page)

    # --- Citations ----------------------------------------------------------------------

    async def citations(self, session: AsyncSession, rows: Sequence[Citation]) -> list[Citation]:
        """Leave out citations of protected people's facts."""
        if not self.restricted or not rows:
            return list(rows)

        def ids(kind: CitedEntity) -> set[uuid.UUID]:
            return {c.entity_id for c in rows if c.entity_type == kind}

        hidden: set[uuid.UUID] = set(self.hidden_events | self.hidden_media | self.protected)
        if names := ids(CitedEntity.person_name):
            hidden |= set(
                await session.scalars(
                    select(PersonName.id).where(
                        PersonName.id.in_(names), PersonName.person_id.in_(self.protected)
                    )
                )
            )
        if links := ids(CitedEntity.parent_child):
            hidden |= set(
                await session.scalars(
                    select(ParentChild.id).where(
                        ParentChild.id.in_(links),
                        or_(
                            ParentChild.parent_id.in_(self.protected),
                            ParentChild.child_id.in_(self.protected),
                        ),
                    )
                )
            )
        if couples := ids(CitedEntity.partnership):
            hidden |= set(
                await session.scalars(
                    select(Partnership.id).where(
                        Partnership.id.in_(couples),
                        or_(
                            Partnership.person_a_id.in_(self.protected),
                            Partnership.person_b_id.in_(self.protected),
                        ),
                    )
                )
            )
        return [c for c in rows if c.entity_id not in hidden]


EVERYTHING = Visibility()


async def load(
    session: AsyncSession, tree: Tree, role: TreeRole, *, via_share_link: bool
) -> Visibility:
    if not restricts(tree, role, via_share_link=via_share_link):
        return EVERYTHING
    protected = frozenset(
        await session.scalars(
            select(Person.id).where(
                Person.tree_id == tree.id, Person.is_living.is_(True), Person.deleted_at.is_(None)
            )
        )
    )
    if not protected:
        return Visibility(restricted=True, show_portraits=tree.show_living_portraits)
    events = frozenset(
        await session.scalars(
            select(EventParticipant.event_id)
            .where(EventParticipant.person_id.in_(protected))
            .distinct()
        )
    )
    media = frozenset(
        await session.scalars(
            select(MediaPerson.media_id).where(MediaPerson.person_id.in_(protected)).distinct()
        )
    ) | frozenset(
        pid
        for pid in await session.scalars(
            select(Person.primary_photo_id).where(Person.id.in_(protected))
        )
        if pid is not None
    )
    return Visibility(
        restricted=True,
        show_portraits=tree.show_living_portraits,
        protected=protected,
        hidden_events=events,
        hidden_media=media,
    )
