"""Place pages: list, summary, privacy, merging and undoing a merge (D116)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog
from tests.conftest import ApiClient
from tests.helpers import Ctx
from tests.test_media_api import jpeg, upload

MakeClient = Callable[[], Awaitable[ApiClient]]


async def _family(ctx: Ctx) -> dict[str, Any]:
    kyiv = await ctx.place(
        "Київ",
        latitude=50.4501,
        longitude=30.5234,
        historical_names=[{"name": "Kiev", "until_year": 1991}],
    )
    brovary = await ctx.place("Бровари", latitude=50.5110, longitude=30.7909)  # ~20 km
    lviv = await ctx.place("Львів", latitude=49.8397, longitude=24.0297)
    halyna = await ctx.person(
        "Галина",
        birth={"date": {"year": 1923, "month": 5, "day": 2}, "place_id": kyiv["id"]},
        death={"date": {"year": 2001}, "place_id": lviv["id"]},
    )
    ivan = await ctx.person("Іван", birth={"date": {"year": 1920}}, death={"date": {"year": 1990}})
    olena = await ctx.person("Олена", birth={"date": {"year": 1985}, "place_id": kyiv["id"]})
    resp = await ctx.editor.post(
        f"{ctx.base}/partnerships",
        json={
            "person_a_id": ivan["id"],
            "person_b_id": halyna["id"],
            "type": "marriage",
            "start_date": {"year": 1946},
            "place_id": kyiv["id"],
        },
    )
    assert resp.status_code == 201, resp.text
    residence = await ctx.editor.post(
        f"{ctx.base}/events",
        json={
            "type": "residence",
            "place_id": kyiv["id"],
            "participants": [{"person_id": ivan["id"]}],
        },
    )
    assert residence.status_code == 201, residence.text
    photo = (await upload(ctx, "kyiv.jpg", jpeg(41, 30))).json()
    patched = await ctx.editor.patch(
        f"{ctx.base}/media/{photo['id']}", json={"place_id": kyiv["id"]}
    )
    assert patched.status_code == 200, patched.text
    for title, body in (("Весілля: Київ, 1946", "…"), ("Про Львів", "Інше місто")):
        story = await ctx.editor.post(
            f"{ctx.base}/stories",
            json={"title": title, "body": body, "person_ids": [ivan["id"]], "status": "published"},
        )
        assert story.status_code == 201, story.text
    return {
        "kyiv": kyiv, "brovary": brovary, "lviv": lviv, "halyna": halyna, "ivan": ivan,
        "olena": olena, "photo": photo, "residence": residence.json(),
    }  # fmt: skip


async def test_place_page(ctx: Ctx) -> None:
    f = await _family(ctx)
    page = (await ctx.editor.get(f"{ctx.base}/places/{f['kyiv']['id']}/summary")).json()
    assert page["place"]["historical_names"][0]["name"] == "Kiev"
    assert page["counts"] == {"birth": 2, "marriage": 1, "residence": 1}
    # Dated facts in date order, undated last.
    assert [x["type"] for x in page["facts"]] == ["birth", "marriage", "birth", "residence"]
    assert [p["id"] for p in page["facts"][1]["persons"]] == [f["ivan"]["id"], f["halyna"]["id"]]
    assert {p["display_name"] for p in page["persons"]} == {
        "Галина Коваленко",
        "Іван Коваленко",
        "Олена Коваленко",
    }
    assert [m["id"] for m in page["media"]] == [f["photo"]["id"]]
    assert [s["title"] for s in page["stories"]] == ["Весілля: Київ, 1946"]
    assert [n["place"]["name"] for n in page["nearby"]] == ["Бровари"]
    assert 15 < page["nearby"][0]["distance_km"] < 25

    lviv = (await ctx.editor.get(f"{ctx.base}/places/{f['lviv']['id']}/summary")).json()
    assert lviv["counts"] == {"death": 1}
    assert lviv["nearby"] == []
    assert [s["title"] for s in lviv["stories"]] == ["Про Львів"]
    missing = await ctx.editor.get(f"{ctx.base}/places/{f['olena']['id']}/summary")
    assert missing.status_code == 404


async def test_place_index(ctx: Ctx) -> None:
    f = await _family(ctx)
    index = (await ctx.editor.get(f"{ctx.base}/places/index")).json()
    assert [(i["place"]["name"], i["events"], i["people"]) for i in index] == [
        ("Київ", 4, 3),
        ("Львів", 1, 1),
        ("Бровари", 0, 0),
    ]
    # Historical names and the other script are searched too.
    for q in ("Kiev", "kyiv"):
        found = (await ctx.editor.get(f"{ctx.base}/places/index", params={"q": q})).json()
        assert [i["place"]["id"] for i in found] == [f["kyiv"]["id"]], q


async def test_place_page_hides_living_people_from_share_links(
    ctx: Ctx, make_client: MakeClient
) -> None:
    f = await _family(ctx)
    tag = {"person_id": f["olena"]["id"]}
    assert (
        await ctx.editor.post(f"{ctx.base}/media/{f['photo']['id']}/people", json=tag)
    ).status_code == 200
    link = (await ctx.editor.post(f"{ctx.base}/share-links", json={})).json()
    guest = await make_client()
    await guest.post(f"/api/v1/share/{link['url'].rsplit('/s/', 1)[1]}/open")
    page = (await guest.get(f"{ctx.base}/places/{f['kyiv']['id']}/summary")).json()
    assert page["counts"] == {"birth": 1, "marriage": 1, "residence": 1}
    assert f["olena"]["id"] not in {p["id"] for p in page["persons"]}
    assert page["media"] == []
    index = (await guest.get(f"{ctx.base}/places/index")).json()
    assert (index[0]["events"], index[0]["people"]) == (3, 2)


async def test_merge_moves_everything_and_can_be_undone(ctx: Ctx, session: AsyncSession) -> None:
    f = await _family(ctx)
    old = await ctx.place(
        "Київ (стара назва)",
        region="Київська губернія",
        historical_names=[{"name": "Kijów", "until_year": 1800}],
    )
    sofia = await ctx.person("Софія", birth={"date": {"year": 1900}, "place_id": old["id"]})
    photo = (await upload(ctx, "old.jpg", jpeg(42, 30))).json()
    await ctx.editor.patch(f"{ctx.base}/media/{photo['id']}", json={"place_id": old["id"]})

    same = await ctx.editor.post(
        f"{ctx.base}/places/{old['id']}/merge", json={"target_id": old["id"]}
    )
    assert (same.status_code, same.json()["code"]) == (400, "cannot_merge_into_itself")
    viewer_denied = await ctx.editor.post(
        f"{ctx.base}/places/{old['id']}/merge",
        json={"target_id": "00000000-0000-0000-0000-000000000001"},
    )
    assert viewer_denied.status_code == 404

    merged = await ctx.editor.post(
        f"{ctx.base}/places/{old['id']}/merge", json={"target_id": f["kyiv"]["id"]}
    )
    assert merged.status_code == 200, merged.text
    target = merged.json()
    assert [h["name"] for h in target["historical_names"]] == [
        "Kiev",
        "Київ (стара назва)",
        "Kijów",
    ]
    assert target["region"] == "Київська губернія"  # filled in, the target had none
    assert (await ctx.editor.get(f"{ctx.base}/places/{old['id']}")).status_code == 404
    person = (await ctx.editor.get(f"{ctx.base}/persons/{sofia['id']}")).json()
    assert person["birth"]["place"]["id"] == f["kyiv"]["id"]
    media = (await ctx.editor.get(f"{ctx.base}/media/{photo['id']}")).json()
    assert media["place"]["id"] == f["kyiv"]["id"]
    page = (await ctx.editor.get(f"{ctx.base}/places/{f['kyiv']['id']}/summary")).json()
    assert page["counts"]["birth"] == 3
    entry = await session.scalar(select(AuditLog).where(AuditLog.action == "place.merge"))
    assert entry is not None
    assert entry.after is not None
    assert entry.after["into"] == f["kyiv"]["id"]
    assert len(entry.after["moved"]["events"]) == 1

    # Restoring the merged place from the trash undoes the merge.
    trash = (await ctx.editor.get(f"{ctx.base}/trash")).json()
    assert [(t["entity_type"], t["entity_id"]) for t in trash] == [("place", old["id"])]
    restored = await ctx.editor.post(f"{ctx.base}/trash/place/{old['id']}/restore")
    assert restored.status_code == 204
    person = (await ctx.editor.get(f"{ctx.base}/persons/{sofia['id']}")).json()
    assert person["birth"]["place"]["id"] == old["id"]
    media = (await ctx.editor.get(f"{ctx.base}/media/{photo['id']}")).json()
    assert media["place"]["id"] == old["id"]
    kyiv = (await ctx.editor.get(f"{ctx.base}/places/{f['kyiv']['id']}")).json()
    assert [h["name"] for h in kyiv["historical_names"]] == ["Kiev"]
    assert kyiv["region"] is None
    page = (await ctx.editor.get(f"{ctx.base}/places/{f['kyiv']['id']}/summary")).json()
    assert page["counts"]["birth"] == 2


async def test_only_editors_merge(ctx: Ctx, make_client: MakeClient) -> None:
    f = await _family(ctx)
    link = (await ctx.editor.post(f"{ctx.base}/share-links", json={})).json()
    guest = await make_client()
    await guest.post(f"/api/v1/share/{link['url'].rsplit('/s/', 1)[1]}/open")
    resp = await guest.post(
        f"{ctx.base}/places/{f['lviv']['id']}/merge", json={"target_id": f["kyiv"]["id"]}
    )
    assert resp.status_code == 403
