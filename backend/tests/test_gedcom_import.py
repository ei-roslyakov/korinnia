"""GEDCOM import through the API: upload → preview → confirm (with a merge) → undo."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Person, TreeRole
from app.storage import LocalStorage
from tests.gedcom_samples import SAMPLE
from tests.helpers import Ctx

GED = "application/octet-stream"


@pytest.fixture
def worker(
    session: AsyncSession, local_storage: LocalStorage, monkeypatch: pytest.MonkeyPatch
) -> Any:
    """Runs the queued GEDCOM jobs in-process, on the test session."""
    from app.jobs import tasks

    @asynccontextmanager
    async def factory() -> Any:
        yield session

    monkeypatch.setattr(tasks, "get_sessionmaker", lambda: factory)
    monkeypatch.setattr(tasks, "get_storage", lambda: local_storage)
    return tasks


async def _upload(ctx: Ctx, data: bytes, name: str = "family.ged") -> Any:
    return await ctx.editor.post(f"{ctx.base}/imports", files={"file": (name, data, GED)})


async def test_import_with_merge_and_undo(
    ctx: Ctx, session: AsyncSession, worker: Any, job_queue: Any
) -> None:
    # Already in the tree: Ivan (Latin spelling, born 1890) — the file's @I1@.
    existing = await ctx.person("Ivan", "Kovalenko", gender="male", birth={"date": {"year": 1890}})

    resp = await _upload(ctx, SAMPLE.encode())
    assert resp.status_code == 202, resp.text
    imp = resp.json()
    assert imp["status"] == "analyzing"
    assert [j["task_name"] for j in job_queue.jobs.values()] == ["gedcom.analyze"]

    await worker.analyze_gedcom(import_id=imp["id"])
    imp = (await ctx.editor.get(f"{ctx.base}/imports/{imp['id']}")).json()
    assert imp["status"] == "ready"
    preview = imp["preview"]
    assert preview["encoding"] == "UTF-8"
    assert preview["header"]["source"] == "MyHeritage Family Tree Builder 5.5.1"
    assert preview["counts"] | {} == {
        "persons": 4,
        "families": 1,
        "partnerships": 1,
        "parent_links": 4,
        "events": 9,
        "places": 2,
        "sources": 1,
        "citations": 2,
        "notes": 2,
        "media_links": 1,
    }
    assert {"code": "media_not_imported", "count": 1} in preview["warnings"]
    assert preview["skipped_tags"] == [{"tag": "_CUSTOM", "count": 1}]
    assert [p["name"] for p in preview["people"]][:2] == [
        "Іван Петрович Коваленко",
        "Ганна Мельник",
    ]
    assert preview["duplicates"] == [
        {
            "xref": "@I1@",
            "name": "Іван Петрович Коваленко",
            "years": "1890 – 1944",
            "strong": True,
            "existing": {"id": existing["id"], "name": "Ivan Kovalenko", "years": "1890"},
        }
    ]

    resp = await ctx.editor.post(
        f"{ctx.base}/imports/{imp['id']}/confirm", json={"merge": {"@I1@": existing["id"]}}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "importing"
    await worker.apply_gedcom(import_id=imp["id"])
    imp = (await ctx.editor.get(f"{ctx.base}/imports/{imp['id']}")).json()
    assert imp["status"] == "done", imp
    counts = imp["result"]["counts"]
    assert {k: counts.get(k) for k in ("persons_created", "persons_merged", "partnerships")} == {
        "persons_created": 3,
        "persons_merged": 1,
        "partnerships": 1,
    }
    assert counts["parent_links"] == 4
    assert imp["result"]["warnings"] == []

    # The existing Ivan is kept as he was, now with a wife and two children.
    people = (await ctx.editor.get(f"{ctx.base}/persons", params={"limit": 50})).json()["items"]
    assert len(people) == 4
    by_name = {p["display_name"]: p for p in people}
    ivan = (await ctx.editor.get(f"{ctx.base}/persons/{existing['id']}")).json()
    assert [r["person"]["display_name"] for r in ivan["partners"]] == ["Ганна Мельник"]
    assert sorted(c["person"]["display_name"] for c in ivan["children"]) == [
        "Марія Коваленко",
        "Олександр Іванович Коваленко",
    ]
    maria = (await ctx.editor.get(f"{ctx.base}/persons/{by_name['Марія Коваленко']['id']}")).json()
    assert {p["type"] for p in maria["parents"]} == {"adoptive"}
    assert maria["birth"]["date"]["phrase"] == "Великдень 1922"
    hanna = (await ctx.editor.get(f"{ctx.base}/persons/{by_name['Ганна Мельник']['id']}")).json()
    assert [(n["type"], n["last_name"]) for n in hanna["names"]] == [
        ("birth", "Мельник"),
        ("married", "Коваленко"),
    ]
    places = (await ctx.editor.get(f"{ctx.base}/places")).json()["items"]
    # Only the wedding place: Ivan's own facts stay as they were (he was merged).
    assert [p["name"] for p in places] == ["Полтава"]
    sources = (await ctx.editor.get(f"{ctx.base}/sources")).json()["items"]
    assert [(s["title"], s["citation_count"]) for s in sources] == [
        ("Метрична книга Преображенської церкви", 1)
    ]

    # Undo: what the import created goes to the trash; the existing Ivan stays.
    resp = await ctx.editor.post(f"{ctx.base}/imports/{imp['id']}/undo")
    assert resp.json()["status"] == "undoing"
    await worker.undo_gedcom(import_id=imp["id"])
    assert (await ctx.editor.get(f"{ctx.base}/imports/{imp['id']}")).json()["status"] == "undone"
    alive = list(
        await session.scalars(
            select(Person.id).where(Person.tree_id == ctx.tree.id, Person.deleted_at.is_(None))
        )
    )
    assert [str(i) for i in alive] == [existing["id"]]
    assert len((await ctx.editor.get(f"{ctx.base}/trash")).json()) == 4  # 3 people + source
    history = (await ctx.editor.get(f"{ctx.base}/imports")).json()
    assert [i["status"] for i in history] == ["undone"]


async def test_bad_records_are_skipped_with_warnings(ctx: Ctx, worker: Any, job_queue: Any) -> None:
    # A child with a third and fourth biological parent, and a child who is their own parent.
    ged = """0 HEAD
1 CHAR UTF-8
0 @A@ INDI
1 NAME Anna /Tkach/
0 @B@ INDI
1 NAME Bohdan /Tkach/
0 @C@ INDI
1 NAME Chrystia /Tkach/
0 @D@ INDI
1 NAME Dmytro /Tkach/
0 @K@ INDI
1 NAME Kyrylo /Tkach/
0 @F1@ FAM
1 HUSB @B@
1 WIFE @A@
1 CHIL @K@
0 @F2@ FAM
1 HUSB @D@
1 WIFE @C@
1 CHIL @K@
0 @F3@ FAM
1 HUSB @K@
1 CHIL @K@
0 TRLR
"""
    imp = (await _upload(ctx, ged.encode(), "tkach.ged")).json()
    await worker.analyze_gedcom(import_id=imp["id"])
    await ctx.editor.post(f"{ctx.base}/imports/{imp['id']}/confirm", json={})
    await worker.apply_gedcom(import_id=imp["id"])
    imp = (await ctx.editor.get(f"{ctx.base}/imports/{imp['id']}")).json()
    assert imp["status"] == "done"
    assert imp["result"]["counts"]["persons_created"] == 5
    assert imp["result"]["counts"]["parent_links"] == 2
    reasons = sorted(w["reason"] for w in imp["result"]["warnings"])
    assert reasons == [
        "self_relation",
        "too_many_biological_parents",
        "too_many_biological_parents",
    ]


async def test_upload_checks_and_permissions(
    ctx: Ctx,
    worker: Any,
    make_user: Callable[..., Awaitable[Any]],
    make_client: Callable[[], Awaitable[Any]],
    add_member: Callable[..., Awaitable[Any]],
) -> None:
    resp = await _upload(ctx, b"<html>not a family</html>", "x.ged")
    assert (resp.status_code, resp.json()["code"]) == (422, "not_gedcom")

    imp = (await _upload(ctx, SAMPLE.encode())).json()
    # Not analysed yet: cannot be confirmed.
    resp = await ctx.editor.post(f"{ctx.base}/imports/{imp['id']}/confirm", json={})
    assert resp.json()["code"] == "import_not_ready"
    await worker.analyze_gedcom(import_id=imp["id"])
    resp = await ctx.editor.post(
        f"{ctx.base}/imports/{imp['id']}/confirm",
        json={"merge": {"@I3@": "00000000-0000-0000-0000-000000000000"}},
    )
    assert resp.json()["code"] == "unknown_import_person"
    resp = await ctx.editor.post(f"{ctx.base}/imports/{imp['id']}/cancel")
    assert resp.json()["status"] == "cancelled"

    viewer = await make_user("viewer@example.com")
    await add_member(ctx.tree, viewer, TreeRole.viewer)
    v = await make_client()
    await v.login("viewer@example.com")
    assert (await v.get(f"{ctx.base}/imports")).status_code == 403
    assert (
        await v.post(f"{ctx.base}/imports", files={"file": ("a.ged", SAMPLE.encode(), GED)})
    ).status_code == 403


async def test_unreadable_file_fails_analysis(ctx: Ctx, worker: Any) -> None:
    imp = (await _upload(ctx, b"0 HEAD\n")).json()
    await worker.analyze_gedcom(import_id=imp["id"])
    imp = (await ctx.editor.get(f"{ctx.base}/imports/{imp['id']}")).json()
    assert imp["status"] == "ready"
    assert imp["preview"]["counts"]["persons"] == 0
    bom_utf16 = SAMPLE.encode("utf-16")
    imp = (await _upload(ctx, bom_utf16, "utf16.ged")).json()
    await worker.analyze_gedcom(import_id=imp["id"])
    imp = (await ctx.editor.get(f"{ctx.base}/imports/{imp['id']}")).json()
    assert (imp["status"], imp["preview"]["encoding"]) == ("ready", "UTF-16")
