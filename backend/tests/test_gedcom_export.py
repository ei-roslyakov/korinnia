"""GEDCOM export: format details, privacy option, permissions, and a full round trip through
our own importer (export the demo family, import it into an empty tree, compare)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import seed as seed_module
from app.core.dates import PartialDate
from app.core.enums import DatePrecision
from app.exporters.gedcom import _Lines, gedcom_date
from app.importers.gedcom.parser import parse
from app.importers.gedcom.records import read
from app.models import AuditLog, ParentChild, Partnership, Person, Tree, TreeRole, User
from app.services import trees as tree_service
from app.services.context import Actor
from app.storage import LocalStorage
from tests.conftest import ApiClient

MakeUser = Callable[..., Awaitable[User]]
MakeClient = Callable[[], Awaitable[ApiClient]]


def test_dates() -> None:
    d = PartialDate
    assert gedcom_date(d(1890, 3, 12, DatePrecision.exact)) == "12 MAR 1890"
    assert gedcom_date(d(1890, 3, None, DatePrecision.month)) == "MAR 1890"
    assert gedcom_date(d(1866, None, None, DatePrecision.approx)) == "ABT 1866"
    assert gedcom_date(d(1944, None, None, DatePrecision.before)) == "BEF 1944"
    assert gedcom_date(d(1945, None, None, DatePrecision.after)) == "AFT 1945"
    between = d(1914, None, None, DatePrecision.between, 1918)
    assert gedcom_date(between) == "BET 1914 AND 1918"
    assert gedcom_date(d(precision=DatePrecision.unknown, phrase="at Easter")) == "(at Easter)"
    assert gedcom_date(d(1888, None, None, DatePrecision.year, phrase="Easter (1888)")) == (
        "INT 1888 (Easter [1888])"
    )
    assert gedcom_date(None) is None
    assert gedcom_date(d()) is None


def test_long_and_multi_line_values() -> None:
    w = _Lines()
    w.add(1, "NOTE", "a" * 300 + "\nsecond line, mail@example.com")
    w.add(1, "FAMS", "@F1@")
    lines = w.text().splitlines()
    assert lines[0] == "1 NOTE " + "a" * 240
    assert lines[1] == "2 CONC " + "a" * 60
    assert lines[2] == "2 CONT second line, mail@@example.com"
    assert lines[3] == "1 FAMS @F1@"  # pointers are not escaped


async def _demo(session: AsyncSession, owner: User, storage: LocalStorage) -> Tree:
    tree = await seed_module.seed(session, owner, storage=storage, portraits=False)
    assert tree is not None
    return tree


async def test_round_trip_of_the_demo_family(
    make_user: MakeUser,
    make_client: MakeClient,
    session: AsyncSession,
    local_storage: LocalStorage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = await make_user("owner@example.com", is_superadmin=True)
    tree = await _demo(session, owner, local_storage)
    c = await make_client()
    await c.login("owner@example.com")
    resp = await c.get(f"/api/v1/trees/{tree.id}/export/gedcom")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/x-gedcom")
    assert "attachment" in resp.headers["content-disposition"]
    assert 'filename="rodyna-kovalenkiv-(demo)-' in resp.headers["content-disposition"]
    text = resp.content.decode("utf-8")
    assert text.startswith("0 HEAD\n1 SOUR KORINNIA")
    assert text.rstrip().endswith("0 TRLR")
    assert all(len(line) <= 255 for line in text.splitlines())

    data = read(parse(resp.content))
    assert len(data.persons) == len(seed_module.PEOPLE)
    pairs = sum(1 for f in data.families.values() if f.husband and f.wife)
    assert pairs == len(seed_module.MARRIAGES)
    by_name = {p.display: p for p in data.persons.values()}
    halyna = by_name["Галина Йосипівна Коваленко"]
    assert halyna.vital("birth").date == {  # type: ignore[union-attr]
        "year": 1923, "month": 2, "day": 14, "precision": "exact"
    }  # fmt: skip
    assert [n.last_name for n in halyna.names][:2] == ["Коваленко", "Шевчук"]
    assert by_name["Параска Коваленко"].vital("birth").date["precision"] == "approx"  # type: ignore[union-attr,index]
    stepan = by_name["Степан Коваленко"]
    burial = next(e for e in stepan.events if e.type == "burial")
    assert burial.place is not None
    assert burial.place.startswith("Великі Сорочинці")
    yurii_family = next(
        f for f in data.families.values()
        if data.persons.get(f.husband or "") is by_name["Юрій Миколайович Ткач"]
    )  # fmt: skip
    assert (yurii_family.married, yurii_family.end_reason) == (True, "divorce")
    olena_family = next(
        f for f in data.families.values()
        if f.wife and data.persons[f.wife] is by_name["Олена Юріївна Ткач"] and f.husband
    )  # fmt: skip
    assert olena_family.married is False  # unmarried partners: no MARR

    # Import the file into an empty tree: the same people, couples and parent links.
    from app.jobs import tasks

    @asynccontextmanager
    async def factory() -> Any:
        yield session

    monkeypatch.setattr(tasks, "get_sessionmaker", lambda: factory)
    monkeypatch.setattr(tasks, "get_storage", lambda: local_storage)
    copy = await tree_service.create_tree(
        session, name="Копія", description=None, owner=owner, actor=Actor(owner)
    )
    imp = (
        await c.post(
            f"/api/v1/trees/{copy.id}/imports",
            files={"file": ("demo.ged", resp.content, "application/octet-stream")},
        )
    ).json()
    await tasks.analyze_gedcom(import_id=imp["id"])
    await c.post(f"/api/v1/trees/{copy.id}/imports/{imp['id']}/confirm", json={})
    await tasks.apply_gedcom(import_id=imp["id"])
    result = (await c.get(f"/api/v1/trees/{copy.id}/imports/{imp['id']}")).json()
    assert result["status"] == "done", result
    assert result["result"]["warnings"] == []

    async def count(model: Any, tree_id: Any) -> int:
        return (
            await session.scalar(
                select(func.count())
                .select_from(model)
                .where(model.tree_id == tree_id, model.deleted_at.is_(None))
            )
            or 0
        )

    for model in (Person, ParentChild, Partnership):
        assert await count(model, copy.id) == await count(model, tree.id), model


async def test_living_people_can_be_left_out(
    make_user: MakeUser,
    make_client: MakeClient,
    session: AsyncSession,
    local_storage: LocalStorage,
) -> None:
    owner = await make_user("owner@example.com")
    tree = await _demo(session, owner, local_storage)
    c = await make_client()
    await c.login("owner@example.com")
    full = (await c.get(f"/api/v1/trees/{tree.id}/export/gedcom")).text
    private = (
        await c.get(f"/api/v1/trees/{tree.id}/export/gedcom", params={"living": "false"})
    ).text
    assert "Тарас" in full
    assert "Тарас" not in private
    assert "1 NAME Living /Коваленко/" in private
    data = read(parse(private.encode()))
    assert len(data.persons) == len(seed_module.PEOPLE)  # still in the family
    living = [p for p in data.persons.values() if p.display.startswith("Living")]
    assert living
    assert all(not p.events and not p.notes for p in living)
    assert "Степан" in private  # the dead keep their details
    actions = (await session.scalars(select(AuditLog.action))).all()
    assert actions.count("tree.export") == 2


async def test_who_can_export(
    make_user: MakeUser,
    make_client: MakeClient,
    make_tree: Callable[..., Awaitable[Tree]],
    add_member: Callable[..., Awaitable[Any]],
) -> None:
    owner = await make_user("owner@example.com")
    tree = await make_tree(owner, "Порожній")
    viewer = await make_user("viewer@example.com")
    await add_member(tree, viewer, TreeRole.viewer)
    await make_user("stranger@example.com")
    v = await make_client()
    await v.login("viewer@example.com")
    resp = await v.get(f"/api/v1/trees/{tree.id}/export/gedcom")
    assert resp.status_code == 200
    assert read(parse(resp.content)).persons == {}  # an empty tree is still a valid file
    s = await make_client()
    await s.login("stranger@example.com")
    assert (await s.get(f"/api/v1/trees/{tree.id}/export/gedcom")).status_code == 404
