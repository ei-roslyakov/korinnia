"""Builder operations: adding relatives atomically, layout offsets."""

from __future__ import annotations

import uuid
from typing import Any

from tests.helpers import Ctx, y


async def add(ctx: Ctx, relative: dict[str, Any], first: str = "Новий", **extra: Any) -> Any:
    return await ctx.editor.post(
        f"{ctx.base}/persons",
        json={"names": [{"first_name": first}], "relative": relative, **extra},
    )


async def test_add_parent_child_partner_sibling(ctx: Ctx) -> None:
    kid = await ctx.person("Син", birth={"date": y(1950)})

    resp = await add(ctx, {"person_id": kid["id"], "relation": "parent"}, "Тато", gender="male")
    assert resp.status_code == 201, resp.text
    dad = resp.json()
    assert [c["person"]["id"] for c in dad["children"]] == [kid["id"]]

    resp = await add(
        ctx,
        {"person_id": kid["id"], "relation": "parent", "other_parent_id": dad["id"]},
        "Мама",
        gender="female",
    )
    mom = resp.json()
    assert [p["person"]["id"] for p in mom["partners"]] == [dad["id"]]

    resp = await add(ctx, {"person_id": kid["id"], "relation": "sibling"}, "Сестра")
    sister = resp.json()
    assert {p["person"]["id"] for p in sister["parents"]} == {dad["id"], mom["id"]}
    assert [s["person"]["id"] for s in sister["siblings"]] == [kid["id"]]

    resp = await add(
        ctx,
        {"person_id": kid["id"], "relation": "partner", "partnership_type": "civil_union"},
        "Дружина",
    )
    wife = resp.json()
    assert wife["partners"][0]["type"] == "civil_union"

    resp = await add(
        ctx,
        {
            "person_id": kid["id"],
            "relation": "child",
            "other_parent_id": wife["id"],
            "parent_child_type": "adoptive",
        },
        "Онук",
    )
    grandkid = resp.json()
    assert {(p["person"]["id"], p["type"]) for p in grandkid["parents"]} == {
        (kid["id"], "adoptive"),
        (wife["id"], "adoptive"),
    }


async def test_add_relative_is_atomic(ctx: Ctx) -> None:
    orphan = await ctx.person("Сирота")
    resp = await add(ctx, {"person_id": orphan["id"], "relation": "sibling"})
    assert resp.status_code == 400
    assert resp.json()["code"] == "sibling_needs_parents"

    kid = await ctx.person("Дитина")
    for name in ("Б1", "Б2"):
        assert (
            await add(ctx, {"person_id": kid["id"], "relation": "parent"}, name)
        ).status_code == 201
    resp = await add(ctx, {"person_id": kid["id"], "relation": "parent"}, "Третій")
    assert resp.json()["code"] == "too_many_biological_parents"

    resp = await add(
        ctx,
        {
            "person_id": kid["id"],
            "relation": "parent",
            "other_parent_id": orphan["id"],
            "parent_child_type": "step",
        },
    )
    assert resp.json()["code"] == "invalid_other_parent"
    resp = await add(ctx, {"person_id": str(uuid.uuid4()), "relation": "child"})
    assert resp.json()["code"] == "person_not_found"
    resp = await add(
        ctx, {"person_id": kid["id"], "relation": "child", "other_parent_id": str(uuid.uuid4())}
    )
    assert resp.json()["code"] == "person_not_found"

    # None of the failed attempts left a person behind.
    page = (await ctx.editor.get(f"{ctx.base}/persons")).json()
    assert sorted(p["display_name"] for p in page["items"]) == [
        "Б1",
        "Б2",
        "Дитина Коваленко",
        "Сирота Коваленко",
    ]


async def test_layout_offsets(ctx: Ctx) -> None:
    a = await ctx.person("А")
    url = f"{ctx.base}/layout-offsets/{a['id']}"
    assert (await ctx.editor.put(url, json={"dx": 40.5, "dy": -12})).status_code == 204
    assert (await ctx.editor.put(url, json={"dx": 50, "dy": -10})).status_code == 204
    graph = (await ctx.editor.get(f"{ctx.base}/graph")).json()
    assert graph["layout_offsets"] == {a["id"]: {"dx": 50.0, "dy": -10.0}}
    assert (await ctx.editor.put(url, json={"dx": 0, "dy": 0})).status_code == 204
    assert (await ctx.editor.get(f"{ctx.base}/graph")).json()["layout_offsets"] == {}

    await ctx.editor.put(url, json={"dx": 1, "dy": 1})
    assert (await ctx.editor.delete(f"{ctx.base}/layout-offsets")).status_code == 204
    assert (await ctx.editor.get(f"{ctx.base}/graph")).json()["layout_offsets"] == {}
    resp = await ctx.editor.put(
        f"{ctx.base}/layout-offsets/{uuid.uuid4()}", json={"dx": 1, "dy": 1}
    )
    assert resp.status_code == 404
    assert (await ctx.editor.put(url, json={"dx": 1e9, "dy": 0})).status_code == 422


async def test_layout_offsets_batch(ctx: Ctx) -> None:
    a, b = await ctx.person("А"), await ctx.person("Б")
    await ctx.editor.put(f"{ctx.base}/layout-offsets/{b['id']}", json={"dx": 5, "dy": 5})
    url = f"{ctx.base}/layout-offsets"
    body = {"offsets": {a["id"]: {"dx": 120, "dy": -80}, b["id"]: {"dx": 0, "dy": 0}}}
    assert (await ctx.editor.put(url, json=body)).status_code == 204
    graph = (await ctx.editor.get(f"{ctx.base}/graph")).json()
    assert graph["layout_offsets"] == {a["id"]: {"dx": 120.0, "dy": -80.0}}  # b reset

    # All or nothing: an unknown person rejects the whole batch.
    bad = {"offsets": {a["id"]: {"dx": 1, "dy": 1}, str(uuid.uuid4()): {"dx": 1, "dy": 1}}}
    assert (await ctx.editor.put(url, json=bad)).status_code == 404
    graph = (await ctx.editor.get(f"{ctx.base}/graph")).json()
    assert graph["layout_offsets"][a["id"]] == {"dx": 120.0, "dy": -80.0}
    assert (await ctx.editor.put(url, json={"offsets": {}})).status_code == 204
