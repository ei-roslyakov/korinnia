from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import seed as seed_module
from app.models import ParentChild, Partnership, Person, User
from app.services.genealogy.persons import person_detail


async def test_seed_creates_demo_family(
    session: AsyncSession, make_user: Callable[..., Awaitable[User]]
) -> None:
    owner = await make_user("root@example.com", is_superadmin=True)
    tree = await seed_module.seed(session, owner)
    assert tree is not None

    async def count(model: Any) -> int:
        return (
            await session.scalar(
                select(func.count()).select_from(model).where(model.tree_id == tree.id)
            )
            or 0
        )

    assert await count(Person) == 25
    assert await count(ParentChild) == 29
    assert await count(Partnership) == 9
    assert await seed_module.seed(session, owner) is None  # idempotent
    with_bio = await session.scalar(
        select(func.count()).where(Person.tree_id == tree.id, Person.biography.is_not(None))
    )
    assert with_bio == len(seed_module.BIOGRAPHIES) + 1  # + Halyna's longer one

    # Seeded data is coherent: no implausibility warnings anywhere.
    for person in await session.scalars(select(Person).where(Person.tree_id == tree.id)):
        detail = await person_detail(session, person)
        assert detail.warnings == [], (detail.display_name, detail.warnings)

    halyna = next(
        p
        for p in [
            await person_detail(session, p)
            for p in await session.scalars(select(Person).where(Person.tree_id == tree.id))
        ]
        if p.display_name.startswith("Галина")
    )
    assert halyna.display_name == "Галина Йосипівна Коваленко (Шевчук)"
    assert halyna.birth is not None
    assert halyna.birth.place is not None
    assert halyna.birth.place.name == "Івано-Франківськ"
    assert {n.script.value for n in halyna.names} == {"cyrillic", "latin"}
    assert [s.person.display_name for s in halyna.siblings] == ["Ольга Йосипівна Ткачук (Шевчук)"]


async def test_seed_cli(
    session: AsyncSession, make_user: Callable[..., Awaitable[User]], monkeypatch: Any, capsys: Any
) -> None:
    from contextlib import asynccontextmanager
    from unittest.mock import AsyncMock, MagicMock

    @asynccontextmanager
    async def factory() -> Any:
        yield session

    engine = MagicMock()
    engine.dispose = AsyncMock()
    monkeypatch.setattr(seed_module, "get_sessionmaker", lambda: factory)
    monkeypatch.setattr(seed_module, "get_engine", lambda: engine)
    monkeypatch.setattr(seed_module, "configure_logging", lambda level: None)

    async def run(*argv: str) -> int:
        return await seed_module.run(seed_module.parse_args(list(argv)))

    assert await run() == 1  # no superadmin yet
    await make_user("root@example.com", is_superadmin=True)
    assert await run("--owner", "root@example.com") == 0
    assert "created" in capsys.readouterr().out
    assert await run() == 0
    assert "nothing to do" in capsys.readouterr().out


def test_seed_main_wires_parse_and_run(monkeypatch: Any) -> None:
    seen: list[Any] = []

    async def fake_run(args: Any) -> int:
        seen.append(args)
        return 0

    monkeypatch.setattr(seed_module, "run", fake_run)
    monkeypatch.setattr(seed_module, "configure_logging", lambda level: None)
    assert seed_module.main(["--owner", "x@example.com"]) == 0
    assert seen[0].owner == "x@example.com"
