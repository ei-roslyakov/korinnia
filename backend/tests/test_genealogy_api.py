"""Core genealogical data API: places, persons, events, relationships, history, trash."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import pytest

from app.models import Tree, TreeRole, User
from tests.conftest import ApiClient


@dataclass
class Ctx:
    tree: Tree
    editor: ApiClient
    base: str

    async def person(self, first: str, last: str = "Коваленко", **extra: Any) -> dict[str, Any]:
        body = {"names": [{"first_name": first, "last_name": last}], **extra}
        resp = await self.editor.post(f"{self.base}/persons", json=body)
        assert resp.status_code == 201, resp.text
        return resp.json()  # type: ignore[no-any-return]

    async def link(self, parent: str, child: str, type_: str = "biological") -> dict[str, Any]:
        resp = await self.editor.post(
            f"{self.base}/parent-child",
            json={"parent_id": parent, "child_id": child, "type": type_},
        )
        assert resp.status_code == 201, resp.text
        return resp.json()  # type: ignore[no-any-return]

    async def place(self, name: str, **extra: Any) -> dict[str, Any]:
        resp = await self.editor.post(f"{self.base}/places", json={"name": name, **extra})
        assert resp.status_code == 201, resp.text
        return resp.json()  # type: ignore[no-any-return]


@pytest.fixture
async def ctx(
    make_user: Callable[..., Awaitable[User]],
    make_tree: Callable[..., Awaitable[Tree]],
    make_client: Callable[[], Awaitable[ApiClient]],
) -> Ctx:
    owner = await make_user("owner@example.com")
    tree = await make_tree(owner)
    client = await make_client()
    await client.login("owner@example.com")
    return Ctx(tree=tree, editor=client, base=f"/api/v1/trees/{tree.id}")


def y(year: int, **kw: Any) -> dict[str, Any]:
    return {"year": year, **kw}


# --- Places -----------------------------------------------------------------------------


async def test_places_crud_and_historical_search(ctx: Ctx) -> None:
    ivf = await ctx.place(
        "Івано-Франківськ",
        country="Україна",
        historical_names=[{"name": "Станиславів", "until_year": 1962}],
        latitude="48.922633",
        longitude="24.711117",
    )
    await ctx.place("Kraków", country="Polska")
    for q, expected in [
        ("stanyslaviv", ["Івано-Франківськ"]),
        ("Франк", ["Івано-Франківськ"]),
        ("krakow", ["Kraków"]),
        ("", ["Kraków", "Івано-Франківськ"]),
    ]:
        page = (await ctx.editor.get(f"{ctx.base}/places", params={"q": q})).json()
        assert [p["name"] for p in page["items"]] == expected, q

    resp = await ctx.editor.patch(
        f"{ctx.base}/places/{ivf['id']}", json={"notes": "Обласний центр"}
    )
    assert resp.json()["notes"] == "Обласний центр"
    assert resp.json()["historical_names"][0]["name"] == "Станиславів"
    assert (await ctx.editor.get(f"{ctx.base}/places/{ivf['id']}")).status_code == 200

    resp = await ctx.editor.post(f"{ctx.base}/places", json={"name": "X", "latitude": 10})
    assert resp.status_code == 422  # latitude without longitude
    resp = await ctx.editor.post(
        f"{ctx.base}/places", json={"name": "X", "latitude": 95, "longitude": 0}
    )
    assert resp.status_code == 422


async def test_place_in_use_cannot_be_deleted(ctx: Ctx) -> None:
    place = await ctx.place("Полтава")
    person = await ctx.person("Іван", birth={"date": y(1900), "place_id": place["id"]})
    resp = await ctx.editor.delete(f"{ctx.base}/places/{place['id']}")
    assert resp.status_code == 409
    assert resp.json()["code"] == "place_in_use"
    await ctx.editor.patch(f"{ctx.base}/persons/{person['id']}", json={"birth": None})
    assert (await ctx.editor.delete(f"{ctx.base}/places/{place['id']}")).status_code == 204
    assert (await ctx.editor.get(f"{ctx.base}/places/{place['id']}")).status_code == 404


# --- Persons ----------------------------------------------------------------------------


async def test_create_person_full(ctx: Ctx) -> None:
    poltava = await ctx.place("Полтава")
    kyiv = await ctx.place("Київ")
    body = {
        "gender": "female",
        "names": [
            {
                "first_name": "Галина",
                "patronymic": "Іванівна",
                "last_name": "Коваленко",
                "maiden_name": "Шевчук",
                "type": "married",
                "is_primary": True,
            },
            {
                "first_name": "Halyna",
                "last_name": "Kovalenko",
                "script": "latin",
                "type": "married",
            },
            {"first_name": "Галина", "last_name": "Шевчук", "type": "birth"},
        ],
        "birth": {"date": y(1931, month=2, day=14), "place_id": poltava["id"]},
        "death": {
            "date": y(2019, precision="approx"),
            "place_id": kyiv["id"],
            "description": "Похована на Байковому кладовищі",
        },
        "occupation": "Вчителька",
        "biography": "# Життя\n\nНародилася в Полтаві…",
        "notes_for_descendants": "Бережіть родинні фото.",
        "research_status": "partial",
    }
    resp = await ctx.editor.post(f"{ctx.base}/persons", json=body)
    assert resp.status_code == 201, resp.text
    p = resp.json()
    assert p["display_name"] == "Галина Іванівна Коваленко (Шевчук)"
    assert p["is_living"] is False  # death given
    assert [n["script"] for n in p["names"]] == ["cyrillic", "latin", "cyrillic"]
    assert p["birth"]["date"]["text"] == "1931-02-14"
    assert p["birth"]["place"]["name"] == "Полтава"
    assert p["death"]["date"]["text"] == "abt 2019"
    assert p["death"]["description"].startswith("Похована")
    assert [e["type"] for e in p["events"]] == ["birth", "death"]
    assert p["research_status"] == "partial"
    assert p["warnings"] == []


@pytest.mark.parametrize(
    ("body", "living"),
    [
        ({}, True),
        ({"birth": {"date": {"year": 1850}}}, False),
        ({"birth": {"date": {"year": 1990}}}, True),
        ({"birth": {"date": {"year": 1850}}, "is_living": True}, True),
    ],
)
async def test_is_living_inference(ctx: Ctx, body: dict[str, Any], living: bool) -> None:
    p = await ctx.person("X", **body)
    assert p["is_living"] is living


async def test_person_validation(ctx: Ctx) -> None:
    base = f"{ctx.base}/persons"
    bad = [
        {"names": [{"first_name": " "}]},
        {
            "names": [
                {"first_name": "A", "is_primary": True},
                {"first_name": "B", "is_primary": True},
            ]
        },
        {"birth": {"date": {"year": 1900, "month": 2, "day": 30}}},
        {"gender": "robot"},
    ]
    for body in bad:
        assert (await ctx.editor.post(base, json=body)).status_code == 422, body
    resp = await ctx.editor.post(base, json={"birth": {"place_id": str(uuid.uuid4())}})
    assert resp.json()["code"] == "invalid_place"
    assert (await ctx.editor.get(f"{base}/{uuid.uuid4()}")).json()["code"] == "person_not_found"


async def test_update_person(ctx: Ctx) -> None:
    p = await ctx.person("Петро", birth={"date": y(1920)})
    url = f"{ctx.base}/persons/{p['id']}"
    resp = await ctx.editor.patch(
        url,
        json={
            "names": [{"first_name": "Petro", "last_name": "Kovalenko", "script": "latin"}],
            "death": {"date": y(1944, precision="before")},
            "occupation": "Коваль",
        },
    )
    body = resp.json()
    assert body["display_name"] == "Petro Kovalenko"
    assert body["names"][0]["is_primary"] is True  # first name becomes primary
    assert body["is_living"] is False
    assert body["death"]["date"]["text"] == "bef 1944"
    resp = await ctx.editor.patch(url, json={"death": None, "is_living": False, "biography": None})
    assert resp.json()["death"] is None
    resp = await ctx.editor.patch(url, json={"birth": {"date": y(1921)}})
    assert resp.json()["birth"]["date"]["year"] == 1921
    assert len(resp.json()["events"]) == 1


async def test_search_persons(ctx: Ctx) -> None:
    await ctx.person("Олександр", "Шевчук", birth={"date": y(1925)})
    await ctx.person("Halyna", "Kowalenko", birth={"date": y(1931)})
    await ctx.person("Марія", "Коваленко", death={"date": y(1999)})
    await ctx.editor.post(
        f"{ctx.base}/persons",
        json={"names": [{"first_name": "Ганна", "last_name": "Бойко", "maiden_name": "Мельник"}]},
    )

    async def names(q: str) -> list[str]:
        page = (await ctx.editor.get(f"{ctx.base}/persons", params={"q": q})).json()
        return [s["display_name"] for s in page["items"]]

    assert await names("oleksandr") == ["Олександр Шевчук"]  # Latin query → Cyrillic name
    assert await names("Коваленко") == ["Марія Коваленко"]
    assert await names("kowal") == ["Halyna Kowalenko"]
    assert await names("koval") == ["Марія Коваленко"]
    assert await names("Мельник") == ["Ганна Бойко (Мельник)"]  # maiden name
    assert await names("1931") == ["Halyna Kowalenko"]
    assert await names("Марія 1999") == ["Марія Коваленко"]
    assert await names("nobody") == []
    page = (await ctx.editor.get(f"{ctx.base}/persons", params={"limit": 2})).json()
    assert page["total"] == 4
    assert len(page["items"]) == 2


# --- Events -----------------------------------------------------------------------------


async def test_events_timeline(ctx: Ctx) -> None:
    lviv = await ctx.place("Львів")
    p = await ctx.person("Іван", birth={"date": y(1900)}, death={"date": y(1970)})
    wife = await ctx.person("Олена")
    base = f"{ctx.base}/events"
    resp = await ctx.editor.post(
        base,
        json={
            "type": "military_service",
            "title": "Служба в армії",
            "date": {"year": 1941, "end_year": 1945, "precision": "between"},
            "participants": [{"person_id": p["id"]}],
        },
    )
    assert resp.status_code == 201
    military = resp.json()
    resp = await ctx.editor.post(
        base,
        json={
            "type": "marriage",
            "date": y(1925, month=6),
            "place_id": lviv["id"],
            "participants": [
                {"person_id": p["id"], "role": "principal"},
                {"person_id": wife["id"], "role": "spouse"},
            ],
        },
    )
    marriage = resp.json()
    assert {x["display_name"] for x in marriage["participants"]} == {
        "Іван Коваленко",
        "Олена Коваленко",
    }

    detail = (await ctx.editor.get(f"{ctx.base}/persons/{p['id']}")).json()
    assert [e["type"] for e in detail["events"]] == [
        "birth",
        "marriage",
        "military_service",
        "death",
    ]

    resp = await ctx.editor.patch(
        f"{base}/{military['id']}", json={"date": y(1939), "title": "Мобілізація"}
    )
    assert resp.json()["title"] == "Мобілізація"
    assert (await ctx.editor.get(f"{base}/{military['id']}")).json()["date"]["year"] == 1939
    assert (await ctx.editor.delete(f"{base}/{military['id']}")).status_code == 204
    assert (await ctx.editor.get(f"{base}/{military['id']}")).status_code == 404


async def test_event_validation(ctx: Ctx) -> None:
    p = await ctx.person("Іван", birth={"date": y(1900)})
    q = await ctx.person("Петро")
    base = f"{ctx.base}/events"
    cases = [
        ({"type": "birth", "participants": [{"person_id": p["id"]}]}, 409, "vital_exists"),
        (
            {
                "type": "death",
                "participants": [
                    {"person_id": p["id"]},
                    {"person_id": q["id"], "role": "principal"},
                ],
            },
            400,
            "vital_needs_one_principal",
        ),
        (
            {"type": "custom", "participants": [{"person_id": p["id"]}, {"person_id": p["id"]}]},
            400,
            "duplicate_participant",
        ),
        (
            {"type": "custom", "participants": [{"person_id": str(uuid.uuid4())}]},
            404,
            "person_not_found",
        ),
    ]
    for body, status, code in cases:
        resp = await ctx.editor.post(base, json=body)
        assert (resp.status_code, resp.json().get("code")) == (status, code), body
    resp = await ctx.editor.post(base, json={"type": "custom", "participants": []})
    assert resp.status_code == 422
    # A death event via the events API becomes the person's death.
    resp = await ctx.editor.post(
        base, json={"type": "death", "date": y(1980), "participants": [{"person_id": q["id"]}]}
    )
    assert resp.status_code == 201
    detail = (await ctx.editor.get(f"{ctx.base}/persons/{q['id']}")).json()
    assert detail["death"]["date"]["year"] == 1980
    # Changing participants re-validates.
    resp = await ctx.editor.patch(
        f"{base}/{resp.json()['id']}", json={"participants": [{"person_id": str(uuid.uuid4())}]}
    )
    assert resp.status_code == 404


async def test_event_warnings_in_person(ctx: Ctx) -> None:
    p = await ctx.person("Іван", birth={"date": y(1900)}, death={"date": y(1950)})
    await ctx.editor.post(
        f"{ctx.base}/events",
        json={"type": "graduation", "date": y(1890), "participants": [{"person_id": p["id"]}]},
    )
    await ctx.editor.post(
        f"{ctx.base}/events",
        json={"type": "residence", "date": y(1960), "participants": [{"person_id": p["id"]}]},
    )
    detail = (await ctx.editor.get(f"{ctx.base}/persons/{p['id']}")).json()
    assert sorted(w["code"] for w in detail["warnings"]) == [
        "event_after_death",
        "event_before_birth",
    ]


# --- Relationships ----------------------------------------------------------------------


async def test_parent_child_rules(ctx: Ctx) -> None:
    grandpa = await ctx.person("Дід", birth={"date": y(1880)})
    dad = await ctx.person("Тато", gender="male", birth={"date": y(1910)})
    mom = await ctx.person("Мама", gender="female", birth={"date": y(1912)})
    kid = await ctx.person("Син", birth={"date": y(1940)})
    stepdad = await ctx.person("Вітчим")

    await ctx.link(grandpa["id"], dad["id"])
    await ctx.link(dad["id"], kid["id"])
    await ctx.link(mom["id"], kid["id"])
    base = f"{ctx.base}/parent-child"

    async def err(body: dict[str, Any]) -> tuple[int, str]:
        resp = await ctx.editor.post(base, json=body)
        return resp.status_code, resp.json().get("code")

    assert await err({"parent_id": kid["id"], "child_id": kid["id"]}) == (400, "self_relation")
    assert await err({"parent_id": dad["id"], "child_id": kid["id"]}) == (
        409,
        "relationship_exists",
    )
    assert await err({"parent_id": kid["id"], "child_id": grandpa["id"]}) == (
        409,
        "relationship_cycle",
    )
    assert await err({"parent_id": stepdad["id"], "child_id": kid["id"]}) == (
        409,
        "too_many_biological_parents",
    )
    assert await err({"parent_id": str(uuid.uuid4()), "child_id": kid["id"]}) == (
        404,
        "person_not_found",
    )
    step = await ctx.link(stepdad["id"], kid["id"], "step")
    resp = await ctx.editor.patch(f"{base}/{step['id']}", json={"type": "biological"})
    assert resp.json()["code"] == "too_many_biological_parents"
    resp = await ctx.editor.patch(
        f"{base}/{step['id']}", json={"type": "adoptive", "notes": "з 1950"}
    )
    assert resp.json()["type"] == "adoptive"
    assert (await ctx.editor.delete(f"{base}/{step['id']}")).status_code == 204
    assert (await ctx.editor.patch(f"{base}/{step['id']}", json={})).status_code == 404


async def test_relationship_warnings(ctx: Ctx) -> None:
    parent = await ctx.person("Батько", gender="male", birth={"date": y(1900)})
    young = await ctx.person("Дитина", birth={"date": y(1905)})
    old = await ctx.person("Старший", birth={"date": y(1890)})
    resp = await ctx.editor.post(
        f"{ctx.base}/parent-child", json={"parent_id": parent["id"], "child_id": young["id"]}
    )
    assert [w["code"] for w in resp.json()["warnings"]] == ["parent_too_young"]
    assert resp.json()["warnings"][0]["params"]["age"] == 5
    link = await ctx.link(parent["id"], old["id"])
    assert [w["code"] for w in link["warnings"]] == ["child_born_before_parent"]
    detail = (await ctx.editor.get(f"{ctx.base}/persons/{parent['id']}")).json()
    assert sorted(w["code"] for w in detail["warnings"]) == [
        "child_born_before_parent",
        "parent_too_young",
    ]


async def test_partnerships_and_family_view(ctx: Ctx) -> None:
    lviv = await ctx.place("Львів")
    dad = await ctx.person("Тато", gender="male", birth={"date": y(1910)})
    mom = await ctx.person("Мама", gender="female", birth={"date": y(1912)})
    second = await ctx.person("Друга дружина", gender="female")
    a = await ctx.person("Андрій", birth={"date": y(1935)})
    b = await ctx.person("Богдан", birth={"date": y(1938)})
    c = await ctx.person("Христина", birth={"date": y(1950)})
    for kid in (a, b):
        await ctx.link(dad["id"], kid["id"])
        await ctx.link(mom["id"], kid["id"])
    await ctx.link(dad["id"], c["id"])
    await ctx.link(second["id"], c["id"])

    base = f"{ctx.base}/partnerships"
    resp = await ctx.editor.post(
        base,
        json={
            "person_a_id": dad["id"],
            "person_b_id": mom["id"],
            "start_date": y(1933, month=9),
            "place_id": lviv["id"],
            "end_date": y(1945),
            "end_reason": "death",
        },
    )
    assert resp.status_code == 201
    marriage = resp.json()
    assert marriage["type"] == "marriage"
    assert marriage["place"]["name"] == "Львів"
    resp = await ctx.editor.post(
        base, json={"person_a_id": dad["id"], "person_b_id": second["id"], "type": "partnership"}
    )
    second_p = resp.json()
    resp = await ctx.editor.post(base, json={"person_a_id": dad["id"], "person_b_id": dad["id"]})
    assert resp.json()["code"] == "self_relation"

    detail = (await ctx.editor.get(f"{ctx.base}/persons/{a['id']}")).json()
    assert {p["person"]["display_name"] for p in detail["parents"]} == {
        "Тато Коваленко",
        "Мама Коваленко",
    }
    assert [(s["person"]["display_name"], s["half"]) for s in detail["siblings"]] == [
        ("Богдан Коваленко", False),
        ("Христина Коваленко", True),
    ]
    dad_detail = (await ctx.editor.get(f"{ctx.base}/persons/{dad['id']}")).json()
    assert [c["person"]["display_name"] for c in dad_detail["children"]] == [
        "Андрій Коваленко",
        "Богдан Коваленко",
        "Христина Коваленко",
    ]
    assert [p["person"]["display_name"] for p in dad_detail["partners"]] == [
        "Мама Коваленко",
        "Друга дружина Коваленко",
    ]
    assert dad_detail["partners"][0]["end_reason"] == "death"

    resp = await ctx.editor.patch(
        f"{base}/{second_p['id']}",
        json={"type": "marriage", "start_date": y(1948), "notes": "Друга сім'я", "place_id": None},
    )
    assert resp.json()["start_date"]["text"] == "1948"
    assert (await ctx.editor.delete(f"{base}/{second_p['id']}")).status_code == 204
    assert (await ctx.editor.delete(f"{base}/{second_p['id']}")).status_code == 404

    graph = (await ctx.editor.get(f"{ctx.base}/graph")).json()
    assert len(graph["persons"]) == 6
    assert len(graph["parent_child"]) == 6
    assert len(graph["partnerships"]) == 1


# --- Delete, trash, history ------------------------------------------------------------


async def test_delete_person_trash_and_restore(ctx: Ctx) -> None:
    dad = await ctx.person("Тато", birth={"date": y(1910)})
    kid = await ctx.person("Син")
    other = await ctx.person("Сусід")
    await ctx.link(dad["id"], kid["id"])
    await ctx.editor.post(
        f"{ctx.base}/partnerships", json={"person_a_id": dad["id"], "person_b_id": other["id"]}
    )
    await ctx.editor.post(
        f"{ctx.base}/events",
        json={
            "type": "custom",
            "participants": [{"person_id": dad["id"]}, {"person_id": other["id"]}],
        },
    )
    preview = (await ctx.editor.get(f"{ctx.base}/persons/{dad['id']}/delete-preview")).json()
    assert preview["child_links"] == 1
    assert preview["parent_links"] == 0
    assert preview["partnerships"] == 1
    assert preview["events"] == 1  # birth (only participant)
    assert preview["shared_events"] == 1

    assert (await ctx.editor.delete(f"{ctx.base}/persons/{dad['id']}")).status_code == 204
    assert (await ctx.editor.get(f"{ctx.base}/persons/{dad['id']}")).status_code == 404
    kid_detail = (await ctx.editor.get(f"{ctx.base}/persons/{kid['id']}")).json()
    assert kid_detail["parents"] == []
    graph = (await ctx.editor.get(f"{ctx.base}/graph")).json()
    assert len(graph["persons"]) == 2
    assert graph["parent_child"] == []

    trash = (await ctx.editor.get(f"{ctx.base}/trash")).json()
    assert [(t["entity_type"], t["label"], t["batch_size"]) for t in trash] == [
        ("person", "Тато Коваленко", 4)
    ]
    assert trash[0]["deleted_by"] == "owner@example.com"

    resp = await ctx.editor.post(f"{ctx.base}/trash/person/{dad['id']}/restore")
    assert resp.status_code == 204
    detail = (await ctx.editor.get(f"{ctx.base}/persons/{dad['id']}")).json()
    assert detail["birth"]["date"]["year"] == 1910
    assert [c["person"]["id"] for c in detail["children"]] == [kid["id"]]
    assert len(detail["partners"]) == 1
    assert (await ctx.editor.get(f"{ctx.base}/trash")).json() == []
    resp = await ctx.editor.post(f"{ctx.base}/trash/person/{dad['id']}/restore")
    assert resp.json()["code"] == "not_in_trash"


async def test_trash_lists_relationships_events_and_places(ctx: Ctx) -> None:
    a, b = await ctx.person("А"), await ctx.person("Б")
    link = await ctx.link(a["id"], b["id"])
    p = (
        await ctx.editor.post(
            f"{ctx.base}/partnerships", json={"person_a_id": a["id"], "person_b_id": b["id"]}
        )
    ).json()
    ev = (
        await ctx.editor.post(
            f"{ctx.base}/events",
            json={"type": "award", "date": y(1950), "participants": [{"person_id": a["id"]}]},
        )
    ).json()
    place = await ctx.place("Хутір")
    await ctx.editor.delete(f"{ctx.base}/parent-child/{link['id']}")
    await ctx.editor.delete(f"{ctx.base}/partnerships/{p['id']}")
    await ctx.editor.delete(f"{ctx.base}/events/{ev['id']}")
    await ctx.editor.delete(f"{ctx.base}/places/{place['id']}")
    trash = (await ctx.editor.get(f"{ctx.base}/trash")).json()
    assert {(t["entity_type"], t["label"]) for t in trash} == {
        ("parent_child", "А Коваленко → Б Коваленко"),
        ("partnership", "А Коваленко ⚭ Б Коваленко"),
        ("event", "award 1950"),
        ("place", "Хутір"),
    }
    # A new identical link was created meanwhile: the old one stays in the trash.
    await ctx.link(a["id"], b["id"])
    resp = await ctx.editor.post(f"{ctx.base}/trash/parent_child/{link['id']}/restore")
    assert resp.status_code == 204
    graph = (await ctx.editor.get(f"{ctx.base}/graph")).json()
    assert len(graph["parent_child"]) == 1
    for t in trash:
        if t["entity_type"] != "parent_child":
            r = await ctx.editor.post(
                f"{ctx.base}/trash/{t['entity_type']}/{t['entity_id']}/restore"
            )
            assert r.status_code == 204
    assert (await ctx.editor.get(f"{ctx.base}/places/{place['id']}")).status_code == 200


async def test_history_and_restore_revision(ctx: Ctx) -> None:
    poltava = await ctx.place("Полтава")
    p = await ctx.person(
        "Іван", birth={"date": y(1900), "place_id": poltava["id"]}, occupation="Коваль"
    )
    url = f"{ctx.base}/persons/{p['id']}"
    await ctx.editor.patch(
        url,
        json={
            "names": [{"first_name": "Іоан", "last_name": "Коваленко"}],
            "occupation": "Священник",
            "birth": None,
        },
    )
    history = (
        await ctx.editor.get(
            f"{ctx.base}/history", params={"entity_type": "person", "entity_id": p["id"]}
        )
    ).json()
    assert [e["action"] for e in history["items"]] == ["person.update", "person.create"]
    create_entry = history["items"][1]
    assert create_entry["after"]["names"][0]["first_name"] == "Іван"
    assert create_entry["after"]["birth"]["date"]["year"] == 1900
    assert history["items"][0]["before"]["occupation"] == "Коваль"

    resp = await ctx.editor.post(f"{ctx.base}/history/{create_entry['id']}/restore")
    assert resp.json() == {"entity_type": "person", "entity_id": p["id"]}
    detail = (await ctx.editor.get(url)).json()
    assert detail["display_name"] == "Іван Коваленко"
    assert detail["occupation"] == "Коваль"
    assert detail["birth"]["place"]["name"] == "Полтава"
    history = (
        await ctx.editor.get(
            f"{ctx.base}/history", params={"entity_type": "person", "entity_id": p["id"]}
        )
    ).json()
    assert history["items"][0]["action"] == "person.restore_revision"

    # Restoring a deletion entry (no "after") is refused; deleted entities must use the trash.
    await ctx.editor.delete(url)
    history = (
        await ctx.editor.get(
            f"{ctx.base}/history", params={"entity_type": "person", "entity_id": p["id"]}
        )
    ).json()
    delete_entry, update_entry = history["items"][0], history["items"][1]
    resp = await ctx.editor.post(f"{ctx.base}/history/{delete_entry['id']}/restore")
    assert resp.json()["code"] == "revision_not_restorable"
    resp = await ctx.editor.post(f"{ctx.base}/history/{update_entry['id']}/restore")
    assert resp.json()["code"] == "entity_deleted"
    resp = await ctx.editor.post(f"{ctx.base}/history/{uuid.uuid4()}/restore")
    assert resp.status_code == 404


async def test_restore_revision_other_entities(ctx: Ctx) -> None:
    a, b = await ctx.person("А"), await ctx.person("Б")
    place = await ctx.place("Хутір", notes="старий")
    link = await ctx.link(a["id"], b["id"])
    p = (
        await ctx.editor.post(
            f"{ctx.base}/partnerships",
            json={"person_a_id": a["id"], "person_b_id": b["id"], "start_date": y(1920)},
        )
    ).json()
    ev = (
        await ctx.editor.post(
            f"{ctx.base}/events",
            json={
                "type": "burial",
                "cemetery_name": "Личаківське",
                "latitude": "49.83",
                "longitude": "24.05",
                "participants": [{"person_id": a["id"]}],
            },
        )
    ).json()
    await ctx.editor.patch(f"{ctx.base}/places/{place['id']}", json={"notes": "новий"})
    await ctx.editor.patch(f"{ctx.base}/parent-child/{link['id']}", json={"type": "adoptive"})
    await ctx.editor.patch(f"{ctx.base}/partnerships/{p['id']}", json={"start_date": None})
    await ctx.editor.patch(f"{ctx.base}/events/{ev['id']}", json={"cemetery_name": "Інше"})

    for entity_type, entity_id in [
        ("place", place["id"]),
        ("parent_child", link["id"]),
        ("partnership", p["id"]),
        ("event", ev["id"]),
    ]:
        history = (
            await ctx.editor.get(
                f"{ctx.base}/history",
                params={"entity_type": entity_type, "entity_id": entity_id},
            )
        ).json()
        created = history["items"][-1]
        resp = await ctx.editor.post(f"{ctx.base}/history/{created['id']}/restore")
        assert resp.status_code == 200, (entity_type, resp.text)

    assert (await ctx.editor.get(f"{ctx.base}/places/{place['id']}")).json()["notes"] == "старий"
    assert (await ctx.editor.get(f"{ctx.base}/events/{ev['id']}")).json()[
        "cemetery_name"
    ] == "Личаківське"
    a_detail = (await ctx.editor.get(f"{ctx.base}/persons/{a['id']}")).json()
    assert a_detail["children"][0]["type"] == "biological"
    assert a_detail["partners"][0]["start_date"]["year"] == 1920


# --- Permissions ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("role", "read", "write"),
    [("viewer", 200, 403), ("contributor", 200, 403), ("editor", 200, 201)],
)
async def test_role_permissions(
    ctx: Ctx,
    make_user: Callable[..., Awaitable[User]],
    make_client: Callable[[], Awaitable[ApiClient]],
    add_member: Callable[..., Awaitable[Any]],
    role: str,
    read: int,
    write: int,
) -> None:
    p = await ctx.person("Іван")
    user = await make_user(f"{role}@example.com")
    await add_member(ctx.tree, user, TreeRole(role))
    c = await make_client()
    await c.login(user.email)
    assert (await c.get(f"{ctx.base}/persons/{p['id']}")).status_code == read
    assert (await c.get(f"{ctx.base}/graph")).status_code == read
    resp = await c.post(f"{ctx.base}/persons", json={"names": [{"first_name": "X"}]})
    assert resp.status_code == write
    expected_mutation = 403 if write == 403 else 200
    resp = await c.patch(f"{ctx.base}/persons/{p['id']}", json={"occupation": "x"})
    assert resp.status_code == expected_mutation
    trash_status = 403 if write == 403 else 200
    assert (await c.get(f"{ctx.base}/trash")).status_code == trash_status
    history = (
        await c.get(f"{ctx.base}/history", params={"entity_type": "person", "entity_id": p["id"]})
    ).json()
    assert history["items"][0]["ip_address"] is None  # IPs only for tree admins


async def test_other_trees_data_is_isolated(
    ctx: Ctx,
    make_user: Callable[..., Awaitable[User]],
    make_tree: Callable[..., Awaitable[Tree]],
    make_client: Callable[[], Awaitable[ApiClient]],
) -> None:
    other_owner = await make_user("other@example.com")
    other_tree = await make_tree(other_owner, "Other")
    oc = await make_client()
    await oc.login("other@example.com")
    other_base = f"/api/v1/trees/{other_tree.id}"
    foreign = (
        await oc.post(f"{other_base}/persons", json={"names": [{"first_name": "Чужий"}]})
    ).json()
    foreign_place = (await oc.post(f"{other_base}/places", json={"name": "Чуже"})).json()
    mine = await ctx.person("Свій")
    assert (await ctx.editor.get(f"{ctx.base}/persons/{foreign['id']}")).status_code == 404
    assert (await ctx.editor.get(f"{other_base}/persons/{foreign['id']}")).status_code == 404
    resp = await ctx.editor.post(
        f"{ctx.base}/parent-child", json={"parent_id": mine["id"], "child_id": foreign["id"]}
    )
    assert resp.json()["code"] == "person_not_found"
    resp = await ctx.editor.patch(
        f"{ctx.base}/persons/{mine['id']}", json={"birth": {"place_id": foreign_place["id"]}}
    )
    assert resp.json()["code"] == "invalid_place"
