"""The synthetic large tree used for performance checks (`make perf`)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import perf
from app.exporters.gedcom import export_tree
from app.importers.gedcom.parser import parse
from app.importers.gedcom.records import read
from app.models import ParentChild, Partnership, Person, User


async def test_generator_builds_a_realistic_tree(
    make_user: Callable[..., Awaitable[User]], session: AsyncSession
) -> None:
    owner = await make_user("owner@example.com", is_superadmin=True)
    tree = await perf.build(session, owner, people=400, seed=3)

    async def count(model: Any) -> int:
        return (
            await session.scalar(
                select(func.count()).select_from(model).where(model.tree_id == tree.id)
            )
            or 0
        )

    assert await count(Person) == 400
    assert await count(ParentChild) > 300
    assert await count(Partnership) > 100
    # Many generations and many roots (people without parents), like a real file.
    text = await export_tree(session, tree)
    data = read(parse(text.encode()))
    assert len(data.persons) == 400
    children = {c.xref for f in data.families.values() for c in f.children}
    roots = [x for x in data.persons if x not in children]
    assert len(roots) > 50
    years = [y for p in data.persons.values() if (y := p.year("birth")) is not None]
    assert min(years) < 1815 and max(years) > 1990  # noqa: PT018
    # Same seed, same tree.
    again = await perf.build(session, owner, people=400, seed=3, name="Again")
    first_names = sorted(p.display for p in data.persons.values())
    second = read(parse((await export_tree(session, again)).encode()))
    assert sorted(p.display for p in second.persons.values()) == first_names
