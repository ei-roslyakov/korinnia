"""Privacy of living people for viewers and share-link visitors (D114).

One tree, one living person (Olena) and one deceased (her mother Halyna). Every reading
endpoint is called as a share-link visitor, a viewer and an editor.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, Tree, TreeRole, User
from app.services.genealogy import media as media_service
from app.storage import LocalStorage
from tests.conftest import ApiClient
from tests.helpers import Ctx
from tests.test_media_api import jpeg, upload

MakeClient = Callable[[], Awaitable[ApiClient]]


@dataclass
class Family:
    ctx: Ctx
    living: dict[str, Any]
    deceased: dict[str, Any]
    living_photo: str
    family_photo: str  # shows both
    deceased_photo: str
    living_event: str
    living_story: str
    shared_story: str
    readers: dict[str, ApiClient]  # "guest", "viewer", "editor"

    @property
    def base(self) -> str:
        return self.ctx.base

    async def set_privacy(self, **body: Any) -> None:
        resp = await self.ctx.editor.patch(self.base, json=body)
        assert resp.status_code == 200, resp.text


@pytest.fixture
async def family(
    ctx: Ctx,
    session: AsyncSession,
    local_storage: LocalStorage,
    make_client: MakeClient,
    make_user: Callable[..., Awaitable[User]],
    add_member: Callable[..., Awaitable[Any]],
) -> Family:
    kyiv = await ctx.place("Київ", latitude=50.45, longitude=30.52)
    deceased = await ctx.person(
        "Галина",
        birth={"date": {"year": 1923, "month": 5, "day": 2}, "place_id": kyiv["id"]},
        death={"date": {"year": 2001}},
        biography="Вчителька.",
    )
    living = await ctx.person(
        "Олена",
        birth={"date": {"year": 1985, "month": 3, "day": 14}, "place_id": kyiv["id"]},
        biography="Працює в Києві.",
        occupation="Лікарка",
        religion="—",
    )
    assert living["is_living"] is True
    assert deceased["is_living"] is False
    mother_link = await ctx.link(deceased["id"], living["id"])
    resp = await ctx.editor.post(
        f"{ctx.base}/events",
        json={
            "type": "residence",
            "date": {"year": 2010},
            "place_id": kyiv["id"],
            "participants": [{"person_id": living["id"]}],
        },
    )
    assert resp.status_code == 201, resp.text
    living_event = resp.json()["id"]

    photos = {}
    for i, (key, person_ids) in enumerate(
        (
            ("living", [living["id"]]),
            ("family", [deceased["id"], living["id"]]),
            ("deceased", [deceased["id"]]),
        )
    ):
        media = (await upload(ctx, f"{key}.jpg", jpeg(40 + i, 30))).json()
        for pid in person_ids:
            tagged = await ctx.editor.post(
                f"{ctx.base}/media/{media['id']}/people", json={"person_id": pid}
            )
            assert tagged.status_code == 200, tagged.text
        await media_service.process_media(session, local_storage, uuid.UUID(media["id"]))
        photos[key] = media["id"]
    portrait = await ctx.editor.patch(
        f"{ctx.base}/persons/{living['id']}", json={"primary_photo_id": photos["living"]}
    )
    assert portrait.status_code == 200, portrait.text
    await media_service.make_avatar(session, local_storage, uuid.UUID(living["id"]))

    stories = {}
    for key, person_ids in (
        ("living", [living["id"]]),
        ("shared", [living["id"], deceased["id"]]),
    ):
        resp = await ctx.editor.post(
            f"{ctx.base}/stories",
            json={"title": key, "body": "…", "person_ids": person_ids, "status": "published"},
        )
        assert resp.status_code == 201, resp.text
        stories[key] = resp.json()["id"]

    source = (await ctx.editor.post(f"{ctx.base}/sources", json={"title": "Метрична книга"})).json()
    for entity_type, entity_id in (
        ("person", living["id"]),
        ("person", deceased["id"]),
        ("parent_child", mother_link["id"]),
        ("event", living_event),
    ):
        resp = await ctx.editor.post(
            f"{ctx.base}/citations",
            json={"source_id": source["id"], "entity_type": entity_type, "entity_id": entity_id},
        )
        assert resp.status_code == 201, resp.text
    for body in (
        {"entity_type": "person", "entity_id": living["id"], "body": "Привіт, Олено"},
        {"entity_type": "media", "entity_id": photos["living"], "body": "Гарне фото"},
    ):
        assert (await ctx.editor.post(f"{ctx.base}/comments", json=body)).status_code == 201
    question = {"person_id": living["id"], "question": "Де навчалась?"}
    assert (await ctx.editor.post(f"{ctx.base}/questions", json=question)).status_code == 201

    link = (await ctx.editor.post(f"{ctx.base}/share-links", json={})).json()
    guest = await make_client()
    opened = await guest.post(f"/api/v1/share/{link['url'].rsplit('/s/', 1)[1]}/open")
    assert opened.status_code == 200
    await make_user("viewer@example.com")
    viewer = await make_client()
    await viewer.login("viewer@example.com")
    viewer_user = (await viewer.get("/api/v1/auth/me")).json()
    tree = await session.get(Tree, ctx.tree.id)
    user = await session.get(User, uuid.UUID(viewer_user["id"]))
    await add_member(tree, user, TreeRole.viewer)

    return Family(
        ctx=ctx,
        living=living,
        deceased=deceased,
        living_photo=photos["living"],
        family_photo=photos["family"],
        deceased_photo=photos["deceased"],
        living_event=living_event,
        living_story=stories["living"],
        shared_story=stories["shared"],
        readers={"guest": guest, "viewer": viewer, "editor": ctx.editor},
    )


async def _get(client: ApiClient, url: str, **params: Any) -> Any:
    resp = await client.get(url, params=params)
    assert resp.status_code == 200, resp.text
    return resp.json()


async def assert_restricted(f: Family, reader: ApiClient) -> None:
    """Everything a restricted reader can request about Olena shows only her basics."""
    b, lid, did = f.base, f.living["id"], f.deceased["id"]

    tree = await _get(reader, b)
    assert tree["living_details_hidden"] is True

    page = await _get(reader, f"{b}/persons/{lid}")
    assert page["details_hidden"] is True
    assert page["display_name"] == "Олена Коваленко"
    assert page["gender"] == f.living["gender"]
    assert page["birth"]["date"]["year"] == 1985
    assert page["birth"]["date"]["month"] is None
    assert page["birth"]["date"]["day"] is None
    assert page["birth"]["place"] is None
    for field in ("biography", "occupation", "religion", "avatar_url", "primary_photo_id"):
        assert page[field] is None, field
    assert page["events"] == []
    assert page["media"] == []
    assert page["citations"] == []
    assert page["open_questions"] == []
    assert [s["id"] for s in page["stories"]] == [f.shared_story]
    assert [p["person"]["id"] for p in page["parents"]] == [did]

    # Her mother's page: Olena appears as a child with the basics only; photos showing
    # Olena are gone, Halyna's own photo stays.
    mother = await _get(reader, f"{b}/persons/{did}")
    assert mother["details_hidden"] is False
    assert mother["biography"] == "Вчителька."
    child = mother["children"][0]["person"]
    assert (child["details_hidden"], child["birth"]["text"], child["birth_place"]) == (
        True,
        "1985",
        None,
    )
    assert child["avatar_url"] is None
    assert [m["id"] for m in mother["media"]] == [f.deceased_photo]
    assert len(mother["citations"]) == 1

    graph = await _get(reader, f"{b}/graph")
    summary = next(p for p in graph["persons"] if p["id"] == lid)
    assert summary["details_hidden"] is True
    assert summary["birth"]["day"] is None
    assert summary["avatar_url"] is None

    found = await _get(reader, f"{b}/persons", q="Олена")
    assert found["items"][0]["birth"]["text"] == "1985"

    # Events, photos, documents, files and the portrait cannot be fetched directly.
    for url in (
        f"{b}/events/{f.living_event}",
        f"{b}/media/{f.living_photo}",
        f"{b}/media/{f.family_photo}",
        f"{b}/media/{f.living_photo}/file/original",
        f"{b}/media/{f.family_photo}/file/thumb",
        f"{b}/persons/{lid}/avatar",
        f"{b}/stories/{f.living_story}",
    ):
        assert (await reader.get(url)).status_code == 404, url
    assert (await reader.get(f"{b}/media/{f.deceased_photo}/file/thumb")).status_code == 200

    media = await _get(reader, f"{b}/media")
    assert [m["id"] for m in media["items"]] == [f.deceased_photo]
    assert media["total"] == 1
    assert (await _get(reader, f"{b}/media", person_id=lid))["items"] == []
    album = await _get(reader, f"{b}/album")
    assert [m["id"] for m in album["items"]] == [f.deceased_photo]

    stories = await _get(reader, f"{b}/stories")
    assert [s["id"] for s in stories["items"]] == [f.shared_story]
    shared = await _get(reader, f"{b}/stories/{f.shared_story}")
    olena = next(p for p in shared["persons"] if p["id"] == lid)
    assert olena["details_hidden"] is True

    timeline = await _get(reader, f"{b}/timeline")
    assert all(lid not in [p["id"] for p in i["persons"]] for i in timeline["items"])
    assert {i["type"] for i in timeline["items"]} == {"birth", "death"}
    map_data = await _get(reader, f"{b}/map")
    pins = [fact for point in map_data["points"] for fact in point["facts"]]
    assert all(lid not in [p["id"] for p in fact["persons"]] for fact in pins)
    assert len(pins) == 1  # Halyna's birth in Kyiv
    on_day = await _get(reader, f"{b}/on-this-day", date="2026-03-14")
    assert on_day["items"] == []

    kin = await _get(reader, f"{b}/relationship", a=did, b=lid)
    assert kin["b"]["details_hidden"] is True
    assert kin["b"]["birth"]["month"] is None

    assert await _get(reader, f"{b}/comments", entity_type="person", entity_id=lid) == []
    media_comments = {"entity_type": "media", "entity_id": f.living_photo}
    assert await _get(reader, f"{b}/comments", **media_comments) == []
    assert await _get(reader, f"{b}/questions") == []
    citations = await _get(reader, f"{b}/citations")
    assert [c["target"]["entity_id"] for c in citations] == [did]
    history = await _get(reader, f"{b}/history", entity_type="person", entity_id=lid)
    assert history["items"] == []


async def assert_everything(f: Family, reader: ApiClient) -> None:
    b, lid = f.base, f.living["id"]
    assert (await _get(reader, b))["living_details_hidden"] is False
    page = await _get(reader, f"{b}/persons/{lid}")
    assert page["details_hidden"] is False
    assert page["biography"] == "Працює в Києві."
    assert page["birth"]["date"]["day"] == 14
    assert page["birth"]["place"]["name"] == "Київ"
    assert len(page["events"]) == 2
    assert len(page["media"]) == 2
    assert len(page["citations"]) == 3
    assert {s["id"] for s in page["stories"]} == {f.living_story, f.shared_story}
    assert "/avatar" in page["avatar_url"]
    for url in (
        f"{b}/events/{f.living_event}",
        f"{b}/media/{f.living_photo}/file/thumb",
        f"{b}/persons/{lid}/avatar",
        f"{b}/stories/{f.living_story}",
    ):
        assert (await reader.get(url)).status_code == 200, url
    assert (await _get(reader, f"{b}/album"))["total"] == 3
    assert len(await _get(reader, f"{b}/comments", entity_type="person", entity_id=lid)) == 1
    assert len(await _get(reader, f"{b}/questions")) == 1
    on_day = await _get(reader, f"{b}/on-this-day", date="2026-03-14")
    assert [i["fact"]["persons"][0]["id"] for i in on_day["items"]] == [lid]


async def test_share_link_visitors_see_only_the_basics_by_default(family: Family) -> None:
    assert (await _get(family.ctx.editor, family.base))["living_privacy"] == "share_links"
    await assert_restricted(family, family.readers["guest"])
    await assert_everything(family, family.readers["viewer"])
    await assert_everything(family, family.readers["editor"])


async def test_viewers_too_when_the_admin_chooses(family: Family) -> None:
    await family.set_privacy(living_privacy="viewers_and_share_links")
    await assert_restricted(family, family.readers["guest"])
    await assert_restricted(family, family.readers["viewer"])
    await assert_everything(family, family.readers["editor"])


async def test_nobody_when_turned_off(family: Family) -> None:
    await family.set_privacy(living_privacy="off")
    await assert_everything(family, family.readers["guest"])
    await assert_everything(family, family.readers["viewer"])


async def test_portraits_of_living_people_can_be_shown(family: Family) -> None:
    await family.set_privacy(show_living_portraits=True)
    guest, b, lid = family.readers["guest"], family.base, family.living["id"]
    page = await _get(guest, f"{b}/persons/{lid}")
    assert "/avatar" in page["avatar_url"]
    assert (await guest.get(page["avatar_url"])).status_code == 200
    # Only the cropped portrait: the photo itself stays hidden.
    assert page["media"] == []
    assert page["primary_photo_id"] is None
    assert (await guest.get(f"{b}/media/{family.living_photo}/file/thumb")).status_code == 404


async def test_gedcom_export_hides_living_people_for_restricted_readers(
    family: Family,
) -> None:
    await family.set_privacy(living_privacy="viewers_and_share_links")
    text = (await family.readers["viewer"].get(f"{family.base}/export/gedcom")).text
    assert "Олена" not in text
    assert "Галина" in text
    full = (await family.readers["editor"].get(f"{family.base}/export/gedcom")).text
    assert "Олена" in full


async def test_only_admins_change_the_setting(family: Family, session: AsyncSession) -> None:
    viewer = family.readers["viewer"]
    resp = await viewer.patch(family.base, json={"living_privacy": "off"})
    assert resp.status_code == 403
    resp = await family.ctx.editor.patch(family.base, json={"living_privacy": "nobody"})
    assert resp.status_code == 422
    await family.set_privacy(living_privacy="off", show_living_portraits=True)
    tree = await _get(family.ctx.editor, family.base)
    assert (tree["living_privacy"], tree["show_living_portraits"]) == ("off", True)
    entry = (
        await session.scalars(
            select(AuditLog)
            .where(AuditLog.action == "tree.update")
            .order_by(AuditLog.created_at.desc())
        )
    ).first()
    assert entry is not None
    assert entry.after == {"living_privacy": "off", "show_living_portraits": True}


async def test_tree_list_covers_skip_living_portraits_for_restricted_viewers(
    family: Family,
) -> None:
    viewer = family.readers["viewer"]
    assert len((await _get(viewer, "/api/v1/trees"))[0]["cover"]) == 1
    await family.set_privacy(living_privacy="viewers_and_share_links")
    assert (await _get(viewer, "/api/v1/trees"))[0]["cover"] == []
    assert len((await _get(family.ctx.editor, "/api/v1/trees"))[0]["cover"]) == 1
