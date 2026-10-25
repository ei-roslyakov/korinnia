from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import seed as seed_module
from app.core.config import get_settings
from app.models import MediaFile, ParentChild, Partnership, Person, PersonName, Tree, User
from app.services import trees as tree_service
from app.services.context import Actor
from app.services.demo_portraits import ERAS, era_of, render_portrait
from app.services.genealogy.persons import person_detail
from app.storage import LocalStorage


async def test_seed_creates_demo_family(
    session: AsyncSession,
    make_user: Callable[..., Awaitable[User]],
    local_storage: LocalStorage,
    job_queue: Any,
) -> None:
    owner = await make_user("root@example.com", is_superadmin=True)
    tree = await seed_module.seed(session, owner, storage=local_storage)
    assert tree is not None
    assert tree.is_demo

    async def count(model: Any) -> int:
        return (
            await session.scalar(
                select(func.count()).select_from(model).where(model.tree_id == tree.id)
            )
            or 0
        )

    n = len(seed_module.PEOPLE)
    assert n == 66
    assert await count(Person) == n
    links = sum(len(parents) * len(children) for parents, children in seed_module.FAMILIES)
    assert await count(ParentChild) == links
    assert await count(Partnership) == len(seed_module.MARRIAGES)
    assert tree.description == seed_module.DESCRIPTION
    assert await seed_module.seed(session, owner, storage=local_storage) is None  # idempotent

    # Everyone has a biography and an illustrated portrait (processed by the worker).
    people = list(await session.scalars(select(Person).where(Person.tree_id == tree.id)))
    assert all(p.biography for p in people)
    assert all(p.primary_photo_id and p.primary_photo_crop for p in people)
    assert await count(MediaFile) == n
    # Every portrait is described for the family album: name, biography, year, place.
    portraits = list(await session.scalars(select(MediaFile).where(MediaFile.tree_id == tree.id)))
    assert all(m.title and m.description and m.date_sort for m in portraits)
    assert sum(m.place_id is not None for m in portraits) > n // 2
    stepan = next(m for m in portraits if m.title == "Степан Коваленко")
    assert stepan.description is not None
    assert stepan.description.startswith("Сільський коваль у Великих Сорочинцях.")
    assert stepan.date.precision is not None
    assert stepan.date.precision.value == "approx"
    tasks = [j["task_name"] for j in job_queue.jobs.values()]
    # Previews and portraits come from one job per copy.
    assert tasks.count("demo.portraits") == 1

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
    session: AsyncSession,
    make_user: Callable[..., Awaitable[User]],
    monkeypatch: Any,
    capsys: Any,
    local_storage: LocalStorage,
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
    monkeypatch.setattr(seed_module, "get_storage", lambda: local_storage)

    async def run(*argv: str) -> int:
        return await seed_module.run(seed_module.parse_args(list(argv)))

    async def seed_without_portraits(*args: Any, **kwargs: Any) -> Any:
        return await original_seed(*args, **{**kwargs, "portraits": False})

    original_seed = seed_module.seed
    monkeypatch.setattr(seed_module, "seed", seed_without_portraits)

    assert await run() == 1  # no superadmin yet
    await make_user("root@example.com", is_superadmin=True)
    assert await run("--owner", "root@example.com") == 0
    assert "created" in capsys.readouterr().out
    assert await run() == 0
    # The copy was made without portraits; a re-run fills them in.
    assert f"added biographies / portraits for {len(seed_module.PEOPLE)} people" in (
        capsys.readouterr().out
    )
    assert await run() == 0
    out = capsys.readouterr().out
    assert "already has" in out
    assert "added" not in out

    # --all-users: everyone without a copy gets one.
    await make_user("aunt@example.com")
    assert await run("--all-users") == 0
    out = capsys.readouterr().out
    assert "root@example.com already has" in out
    assert "created" in out
    assert "aunt@example.com" in out

    # A copy created concurrently (unique per owner) is reported, not a crash.
    async def racing(*args: Any, **kwargs: Any) -> Any:
        from sqlalchemy.exc import IntegrityError

        raise IntegrityError("insert", {}, Exception("uq_trees_demo_owner"))

    monkeypatch.setattr(seed_module, "seed", racing)
    assert await run("--owner", "root@example.com") == 0
    assert "already has" in capsys.readouterr().out


def test_seed_main_wires_parse_and_run(monkeypatch: Any) -> None:
    seen: list[Any] = []

    async def fake_run(args: Any) -> int:
        seen.append(args)
        return 0

    monkeypatch.setattr(seed_module, "run", fake_run)
    monkeypatch.setattr(seed_module, "configure_logging", lambda level: None)
    assert seed_module.main(["--owner", "x@example.com"]) == 0
    assert seen[0].owner == "x@example.com"


async def test_each_user_gets_their_own_copy(
    session: AsyncSession,
    make_user: Callable[..., Awaitable[User]],
    local_storage: LocalStorage,
) -> None:
    admin = await make_user("root@example.com", is_superadmin=True)
    aunt = await make_user("aunt@example.com")
    mine = await seed_module.seed(session, admin, storage=local_storage, portraits=False)
    theirs = await seed_module.seed(session, aunt, storage=local_storage, portraits=False)
    assert mine
    assert theirs
    assert mine.id != theirs.id

    # Each sees only their own copy; a superadmin is not flooded with everyone's copies.
    aunt_trees = [t.id for t, _ in await tree_service.list_trees_for_user(session, aunt)]
    assert aunt_trees == [theirs.id]
    admin_trees = [t.id for t, _ in await tree_service.list_trees_for_user(session, admin)]
    assert admin_trees == [mine.id]

    # Deleting the copy lets the user get a fresh one later.
    await tree_service.delete_tree(session, theirs, Actor(aunt))
    again = await seed_module.seed(session, aunt, storage=local_storage, portraits=False)
    assert again is not None
    assert again.id != theirs.id
    assert (
        await session.scalar(
            select(func.count()).where(Tree.owner_id == aunt.id, Tree.is_demo.is_(True))
        )
        == 2  # the deleted one stays in the trash
    )


async def test_new_accounts_queue_a_demo_family(
    make_user: Callable[..., Awaitable[User]],
    monkeypatch: pytest.MonkeyPatch,
    job_queue: Any,
) -> None:
    monkeypatch.setenv("DEMO_TREE_FOR_NEW_USERS", "true")
    get_settings.cache_clear()
    try:
        user = await make_user("new@example.com")
    finally:
        monkeypatch.setenv("DEMO_TREE_FOR_NEW_USERS", "false")
        get_settings.cache_clear()
    jobs = [j for j in job_queue.jobs.values() if j["task_name"] == "demo.create_for_user"]
    assert [j["args"] for j in jobs] == [{"user_id": str(user.id)}]


async def test_demo_job_creates_the_copy(
    session: AsyncSession,
    make_user: Callable[..., Awaitable[User]],
    local_storage: LocalStorage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from contextlib import asynccontextmanager

    from app.jobs import tasks

    @asynccontextmanager
    async def factory() -> Any:
        yield session

    monkeypatch.setattr(tasks, "get_sessionmaker", lambda: factory)
    monkeypatch.setattr(tasks, "get_storage", lambda: local_storage)
    user = await make_user("cousin@example.com")
    await tasks.create_demo_tree(user_id=str(user.id))
    assert await seed_module.demo_tree_of(session, user) is not None
    await tasks.create_demo_tree(user_id=str(user.id))  # second run: nothing to do
    gone = await make_user("gone@example.com", is_active=False)
    await tasks.create_demo_tree(user_id=str(gone.id))
    assert await seed_module.demo_tree_of(session, gone) is None


def test_portraits_are_deterministic_jpegs() -> None:
    a = render_portrait(
        name="Степан", years="1862 – 1931", gender="male", birth_year=1862, seed=1, age=55
    )
    b = render_portrait(
        name="Степан", years="1862 – 1931", gender="male", birth_year=1862, seed=1, age=55
    )
    assert a == b
    assert a[:3] == b"\xff\xd8\xff"
    # Every era, gender and look renders (the seed picks hairstyle and clothing).
    for seed in range(12):
        for year, gender in [
            (1866, "female"),
            (1923, "female"),
            (1979, "female"),
            (1919, "male"),
            (1975, "male"),
        ]:
            img = render_portrait(
                name="X", years="", gender=gender, birth_year=year, seed=seed, age=20 + seed * 4
            )
            assert img[:3] == b"\xff\xd8\xff"
    other = render_portrait(name="Emily", years="1980", gender="female", birth_year=1980, seed=2)
    assert other != a
    assert [era_of(y) for y in (None, 1862, 1923, 1979)] == ["sepia", "sepia", "faded", "colour"]
    assert set(ERAS) == {"sepia", "faded", "colour"}


async def test_complete_demo_fills_gaps_without_overwriting(
    session: AsyncSession,
    make_user: Callable[..., Awaitable[User]],
    local_storage: LocalStorage,
) -> None:
    owner = await make_user("root@example.com")
    tree = await seed_module.seed(session, owner, storage=local_storage, portraits=False)
    assert tree is not None
    people = {
        p.biography.split()[0] if p.biography else "": p
        for p in await session.scalars(select(Person).where(Person.tree_id == tree.id))
    }
    stepan = people["Сільський"]  # "Сільський коваль…"
    stepan.biography = None
    paraska = people["Господиня"]
    paraska.biography = "Моя власна біографія."
    await session.commit()

    done = await seed_module.complete_demo(session, tree, owner, storage=local_storage)
    assert (done.added, done.updated) == (0, len(seed_module.PEOPLE))
    await session.refresh(stepan)
    await session.refresh(paraska)
    assert stepan.biography == seed_module.BIOGRAPHIES["stepan"]
    assert paraska.biography == "Моя власна біографія."  # never overwritten
    assert stepan.primary_photo_id is not None
    assert (
        await seed_module.complete_demo(session, tree, owner, storage=local_storage)
        == seed_module.DemoUpdate()
    )


async def test_complete_demo_redraws_outdated_generated_portraits(
    session: AsyncSession,
    make_user: Callable[..., Awaitable[User]],
    local_storage: LocalStorage,
) -> None:
    owner = await make_user("root@example.com")
    tree = await seed_module.seed(session, owner, storage=local_storage)
    assert tree is not None
    people = list(await session.scalars(select(Person).where(Person.tree_id == tree.id)))
    old, mine = people[0], people[1]
    # `old` still shows a portrait from the first drawing version…
    old_media = await session.get(MediaFile, old.primary_photo_id)
    assert old_media is not None
    key = old_media.original_filename.removeprefix(f"portrait-v{seed_module.PORTRAIT_VERSION}-")
    old_media.original_filename = f"portrait-{key}"
    # …while `mine` shows a photo the user uploaded.
    my_media = await session.get(MediaFile, mine.primary_photo_id)
    assert my_media is not None
    my_media.original_filename = "grandma-1950.jpg"
    # A portrait from before the album: one title for all, no description yet.
    plain = await session.get(MediaFile, people[2].primary_photo_id)
    assert plain is not None
    title = plain.title
    plain.title, plain.description = seed_module.PORTRAIT_TITLE_OLD, None
    await session.commit()

    done = await seed_module.complete_demo(session, tree, owner, storage=local_storage)
    assert (done.added, done.updated) == (0, 2)
    await session.refresh(plain)
    assert (plain.title, bool(plain.description)) == (title, True)
    await session.refresh(old)
    await session.refresh(old_media)
    await session.refresh(mine)
    assert old.primary_photo_id != old_media.id
    assert old_media.deleted_at is not None  # moved to the trash, not destroyed
    assert mine.primary_photo_id == my_media.id  # the user's choice is kept
    assert (
        await seed_module.complete_demo(session, tree, owner, storage=local_storage)
        == seed_module.DemoUpdate()
    )


async def test_complete_demo_adds_the_people_of_a_newer_version(
    session: AsyncSession,
    make_user: Callable[..., Awaitable[User]],
    local_storage: LocalStorage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A copy made from the first version (25 people) grows into the current one; someone
    the owner deleted stays deleted, and their own description is kept."""
    from app.services.genealogy import trash

    owner = await make_user("root@example.com")
    first = {"stepan", "paraska", "ivan", "hanna", "mariia", "fedir", "yosyp", "kateryna"}
    first |= {"oleksandr", "halyna", "petro", "olha", "mykhailo", "mykola", "volodymyr"}
    first |= {"liudmyla", "tetiana", "andrii_b", "stephen", "andrii", "oksana", "nataliia"}
    first |= {"iryna", "oleh", "emily"}
    full = (seed_module.PEOPLE, seed_module.FAMILIES, seed_module.MARRIAGES, seed_module.EVENTS)
    monkeypatch.setattr(seed_module, "PEOPLE", [p for p in full[0] if p.key in first])
    monkeypatch.setattr(
        seed_module,
        "FAMILIES",
        [
            (tuple(x for x in parents if x in first), [c for c in kids if c in first])
            for parents, kids in full[1]
            if all(x in first for x in (*parents, *kids)) or parents == ("stephen", "sarah")
        ],
    )
    monkeypatch.setattr(
        seed_module, "MARRIAGES", [m for m in full[2] if m[0] in first and m[1] in first]
    )
    monkeypatch.setattr(
        seed_module, "EVENTS", [e for e in full[3] if all(k in first for k in e["who"])]
    )
    tree = await seed_module.seed(session, owner, storage=local_storage, portraits=False)
    assert tree is not None
    assert len(seed_module.PEOPLE) == 25
    tree.description = seed_module.OLD_DESCRIPTION
    await session.commit()
    # The owner moved Emily (who is in both versions) to the trash.
    emily = await session.scalar(
        select(Person)
        .join(PersonName, PersonName.person_id == Person.id)
        .where(Person.tree_id == tree.id, PersonName.first_name == "Emily")
    )
    assert emily is not None
    await trash.delete_person(session, emily, Actor(owner))

    monkeypatch.setattr(seed_module, "PEOPLE", full[0])
    monkeypatch.setattr(seed_module, "FAMILIES", full[1])
    monkeypatch.setattr(seed_module, "MARRIAGES", full[2])
    monkeypatch.setattr(seed_module, "EVENTS", full[3])
    done = await seed_module.complete_demo(session, tree, owner, storage=local_storage)
    assert done.added == 66 - 25
    live = await session.scalar(
        select(func.count())
        .select_from(Person)
        .where(Person.tree_id == tree.id, Person.deleted_at.is_(None))
    )
    assert live == 66 - 1  # Emily stays in the trash
    await session.refresh(tree)
    assert tree.description == seed_module.DESCRIPTION
    # Stepan now has parents, and the new people are linked to the old ones.
    stepan = await session.scalar(
        select(Person)
        .join(PersonName, PersonName.person_id == Person.id)
        .where(Person.tree_id == tree.id, PersonName.first_name == "Степан",
               PersonName.last_name == "Коваленко")
    )  # fmt: skip
    assert stepan is not None
    parents = await session.scalar(
        select(func.count()).select_from(ParentChild).where(ParentChild.child_id == stepan.id)
    )
    assert parents == 2
    # Running it again changes nothing more.
    again = await seed_module.complete_demo(session, tree, owner, storage=local_storage)
    assert again.added == 0
