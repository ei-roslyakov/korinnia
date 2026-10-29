"""Ancestors and descendants for the chart views (D118)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from tests.conftest import ApiClient
from tests.helpers import Ctx


async def _family(ctx: Ctx) -> dict[str, dict[str, Any]]:
    """Two cousins marry (pedigree collapse): their child has the same great-grandparents
    twice.

        Gp ── Gm
         ├─────┐
         A     B          (siblings)
         │     │
        A1 ⚭  B1          (first cousins, married 1970)
            │
           Kid (living)
    """

    async def born(name: str, year: int, **kw: Any) -> dict[str, Any]:
        return await ctx.person(name, birth={"date": {"year": year}}, **kw)

    p = {
        "gp": await born("Степан", 1880, death={"date": {"year": 1950}}),
        "gm": await born("Параска", 1882, death={"date": {"year": 1960}}),
        "a": await born("Іван", 1905, death={"date": {"year": 1980}}),
        "b": await born("Марія", 1908, death={"date": {"year": 1990}}),
        "a1": await born("Петро", 1935, death={"date": {"year": 2000}}),
        "b1": await born("Ганна", 1938, death={"date": {"year": 2010}}),
        "kid": await born("Олена", 1972),
        "spouse": await born("Тарас", 1970),
    }
    for parent, child in (
        ("gp", "a"), ("gm", "a"), ("gp", "b"), ("gm", "b"),
        ("a", "a1"), ("b", "b1"), ("a1", "kid"), ("b1", "kid"),
    ):  # fmt: skip
        await ctx.link(p[parent]["id"], p[child]["id"])
    for a, b, year in (("gp", "gm", 1903), ("a1", "b1", 1970), ("kid", "spouse", 1995)):
        resp = await ctx.editor.post(
            f"{ctx.base}/partnerships",
            json={
                "person_a_id": p[a]["id"],
                "person_b_id": p[b]["id"],
                "type": "marriage",
                "start_date": {"year": year},
            },
        )
        assert resp.status_code == 201, resp.text
    return p


async def _lineage(client: ApiClient, ctx: Ctx, pid: str, **params: Any) -> Any:
    resp = await client.get(f"{ctx.base}/persons/{pid}/lineage", params=params)
    assert resp.status_code == 200, resp.text
    return resp.json()


async def test_ancestors_with_pedigree_collapse(ctx: Ctx) -> None:
    p = await _family(ctx)
    ids = {k: v["id"] for k, v in p.items()}
    out = await _lineage(ctx.editor, ctx, ids["kid"], direction="ancestors", depth=4)
    assert out["root_id"] == ids["kid"]
    assert {x["id"] for x in out["persons"]} == {
        ids[k] for k in ("kid", "a1", "b1", "a", "b", "gp", "gm")
    }
    assert sorted(out["repeated"]) == sorted([ids["gp"], ids["gm"]])
    assert len(out["parent_links"]) == 8
    assert out["partnerships"] == []
    assert out["truncated"] is False

    # Depth counts generations above the root; what lies beyond is flagged.
    two = await _lineage(ctx.editor, ctx, ids["kid"], direction="ancestors", depth=2)
    assert {x["id"] for x in two["persons"]} == {ids[k] for k in ("kid", "a1", "b1", "a", "b")}
    assert two["truncated"] is True
    assert two["repeated"] == []


async def test_descendants_with_partners(ctx: Ctx) -> None:
    p = await _family(ctx)
    ids = {k: v["id"] for k, v in p.items()}
    out = await _lineage(ctx.editor, ctx, ids["gp"], direction="descendants", depth=8)
    assert {x["id"] for x in out["persons"]} == set(ids.values())  # spouse and gm as partners
    years = {
        frozenset((x["person_a_id"], x["person_b_id"])): x["year"] for x in out["partnerships"]
    }
    assert years[frozenset((ids["a1"], ids["b1"]))] == 1970
    assert years[frozenset((ids["kid"], ids["spouse"]))] == 1995
    # The kid is a descendant through both of her parents: one entry per link.
    kid_links = [x for x in out["parent_links"] if x["child_id"] == ids["kid"]]
    assert sorted(x["parent_id"] for x in kid_links) == sorted([ids["a1"], ids["b1"]])
    one = await _lineage(ctx.editor, ctx, ids["gp"], direction="descendants", depth=1)
    assert one["truncated"] is True


async def test_depth_is_capped(ctx: Ctx) -> None:
    p = await _family(ctx)
    pid = p["kid"]["id"]
    url = f"{ctx.base}/persons/{pid}/lineage"
    assert (
        await ctx.editor.get(url, params={"direction": "ancestors", "depth": 10})
    ).status_code == 200
    assert (
        await ctx.editor.get(url, params={"direction": "ancestors", "depth": 11})
    ).status_code == 422
    resp = await ctx.editor.get(url, params={"direction": "descendants", "depth": 9})
    assert (resp.status_code, resp.json()["code"]) == (422, "depth_too_large")
    assert (await ctx.editor.get(url, params={"direction": "sideways"})).status_code == 422
    missing = f"{ctx.base}/persons/{p['spouse']['tree_id']}/lineage"
    assert (await ctx.editor.get(missing)).status_code == 404


async def test_living_people_for_share_links(
    ctx: Ctx, make_client: Callable[[], Awaitable[ApiClient]]
) -> None:
    p = await _family(ctx)
    link = (await ctx.editor.post(f"{ctx.base}/share-links", json={})).json()
    guest = await make_client()
    await guest.post(f"/api/v1/share/{link['url'].rsplit('/s/', 1)[1]}/open")
    out = await _lineage(guest, ctx, p["gp"]["id"], direction="descendants", depth=8)
    kid = next(x for x in out["persons"] if x["id"] == p["kid"]["id"])
    assert kid["details_hidden"] is True
    assert kid["birth"]["text"] == "1972"
    years = {
        frozenset((x["person_a_id"], x["person_b_id"])): x["year"] for x in out["partnerships"]
    }
    assert years[frozenset((p["kid"]["id"], p["spouse"]["id"]))] is None  # both living
    assert years[frozenset((p["a1"]["id"], p["b1"]["id"]))] == 1970
