"""Sources & citations, stories, suggestions, comments, questions, data quality."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Any

import pytest

from app.models import TreeRole, User
from tests.conftest import ApiClient
from tests.helpers import Ctx, y

MakeClient = Callable[[], Awaitable[ApiClient]]


@pytest.fixture
async def roles(
    ctx: Ctx,
    make_user: Callable[..., Awaitable[User]],
    make_client: MakeClient,
    add_member: Callable[..., Awaitable[Any]],
) -> dict[str, ApiClient]:
    """Logged-in clients for each role in ctx.tree (editor = the tree admin)."""
    clients: dict[str, ApiClient] = {"editor": ctx.editor}
    for role in ("viewer", "contributor", "contributor2"):
        user = await make_user(f"{role}@example.com", name=role.capitalize())
        await add_member(
            ctx.tree,
            user,
            TreeRole.contributor if role.startswith("contributor") else TreeRole.viewer,
        )
        c = await make_client()
        await c.login(user.email)
        clients[role] = c
    return clients


async def source(ctx: Ctx, title: str = "Метрична книга, Великі Сорочинці", **extra: Any) -> Any:
    resp = await ctx.editor.post(
        f"{ctx.base}/sources", json={"title": title, "type": "church_record", **extra}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# --- Sources & citations ----------------------------------------------------------------


async def test_sources_crud_and_search(ctx: Ctx) -> None:
    s = await source(
        ctx,
        archive_name="ДАПО",
        reference_number="ф. 1011, оп. 1, спр. 120, арк. 34",
        url="https://example.org/scan",
        notes="Запис про хрещення",
    )
    assert s["citation_count"] == 0
    assert s["media"] == []
    await source(ctx, "Перепис 1897", type="census")

    def titles(page: dict[str, Any]) -> list[str]:
        return [x["title"] for x in page["items"]]

    assert titles(
        (await ctx.editor.get(f"{ctx.base}/sources", params={"q": "metrychna"})).json()
    ) == [s["title"]]
    assert titles((await ctx.editor.get(f"{ctx.base}/sources", params={"q": "1011"})).json()) == [
        s["title"]
    ]
    assert (await ctx.editor.get(f"{ctx.base}/sources")).json()["total"] == 2

    resp = await ctx.editor.post(
        f"{ctx.base}/sources", json={"title": "X", "url": "javascript:alert(1)"}
    )
    assert resp.status_code == 422
    resp = await ctx.editor.patch(
        f"{ctx.base}/sources/{s['id']}", json={"title": "Метрична книга (1890)", "author": None}
    )
    assert resp.json()["title"] == "Метрична книга (1890)"
    assert resp.json()["archive_name"] == "ДАПО"
    resp = await ctx.editor.patch(
        f"{ctx.base}/sources/{s['id']}", json={"media_ids": [str(uuid.uuid4())]}
    )
    assert resp.json()["code"] == "media_not_found"


async def test_citations_on_all_fact_types(ctx: Ctx) -> None:
    s = await source(ctx)
    halyna = await ctx.person("Галина", birth={"date": y(1923)})
    dad = await ctx.person("Йосип")
    link = await ctx.link(dad["id"], halyna["id"])
    partner = await ctx.person("Олександр")
    pship = (
        await ctx.editor.post(
            f"{ctx.base}/partnerships",
            json={"person_a_id": halyna["id"], "person_b_id": partner["id"]},
        )
    ).json()
    targets = [
        ("person", halyna["id"], "occupation"),
        ("person_name", halyna["names"][0]["id"], None),
        ("event", halyna["birth"]["event_id"], None),
        ("parent_child", link["id"], None),
        ("partnership", pship["id"], None),
    ]
    for entity_type, entity_id, field in targets:
        resp = await ctx.editor.post(
            f"{ctx.base}/citations",
            json={
                "source_id": s["id"],
                "entity_type": entity_type,
                "entity_id": entity_id,
                "field": field,
                "page": "арк. 34",
                "quality": "primary",
            },
        )
        assert resp.status_code == 201, (entity_type, resp.text)
    resp = await ctx.editor.post(
        f"{ctx.base}/citations",
        json={
            "source_id": s["id"],
            "entity_type": "event",
            "entity_id": halyna["birth"]["event_id"],
            "page": "арк. 34",
        },
    )
    assert resp.json()["code"] == "citation_exists"
    resp = await ctx.editor.post(
        f"{ctx.base}/citations",
        json={"source_id": s["id"], "entity_type": "event", "entity_id": str(uuid.uuid4())},
    )
    assert resp.json()["code"] == "citation_target_not_found"

    page = (await ctx.editor.get(f"{ctx.base}/persons/{halyna['id']}")).json()
    by_type = {c["target"]["entity_type"]: c for c in page["citations"]}
    assert set(by_type) == {"person", "person_name", "event", "parent_child", "partnership"}
    assert by_type["event"]["target"]["event_type"] == "birth"
    assert by_type["event"]["target"]["date"] == "1923"
    assert by_type["person"]["field"] == "occupation"
    assert by_type["parent_child"]["target"]["label"] == "Йосип Коваленко → Галина Коваленко"
    assert by_type["person_name"]["source"]["type"] == "church_record"
    # The father's page shows the shared relationship citation too.
    dad_page = (await ctx.editor.get(f"{ctx.base}/persons/{dad['id']}")).json()
    assert [c["target"]["entity_type"] for c in dad_page["citations"]] == ["parent_child"]

    cid = by_type["person"]["id"]
    resp = await ctx.editor.patch(
        f"{ctx.base}/citations/{cid}",
        json={"quality": "family_tradition", "notes": "Зі слів бабусі"},
    )
    assert resp.json()["quality"] == "family_tradition"
    listing = (await ctx.editor.get(f"{ctx.base}/citations", params={"source_id": s["id"]})).json()
    assert len(listing) == 5
    assert (await ctx.editor.get(f"{ctx.base}/sources/{s['id']}")).json()["citation_count"] == 5
    assert (await ctx.editor.delete(f"{ctx.base}/citations/{cid}")).status_code == 204
    assert (
        len(
            (
                await ctx.editor.get(
                    f"{ctx.base}/citations",
                    params={"entity_type": "person", "entity_id": halyna["id"]},
                )
            ).json()
        )
        == 0
    )

    # Deleting a source moves its citations to the trash with it; restore brings both back.
    assert (await ctx.editor.delete(f"{ctx.base}/sources/{s['id']}")).status_code == 204
    assert (await ctx.editor.get(f"{ctx.base}/persons/{halyna['id']}")).json()["citations"] == []
    trash = (await ctx.editor.get(f"{ctx.base}/trash")).json()
    labels = {(t["entity_type"], t["batch_size"]) for t in trash}
    assert ("source", 5) in labels
    await ctx.editor.post(f"{ctx.base}/trash/source/{s['id']}/restore")
    assert (
        len((await ctx.editor.get(f"{ctx.base}/persons/{halyna['id']}")).json()["citations"]) == 4
    )


async def test_source_history_restore(ctx: Ctx) -> None:
    s = await source(ctx, "Лист")
    await ctx.editor.patch(f"{ctx.base}/sources/{s['id']}", json={"title": "Лист від Ольги"})
    history = (
        await ctx.editor.get(
            f"{ctx.base}/history", params={"entity_type": "source", "entity_id": s["id"]}
        )
    ).json()
    created = history["items"][-1]
    await ctx.editor.post(f"{ctx.base}/history/{created['id']}/restore")
    assert (await ctx.editor.get(f"{ctx.base}/sources/{s['id']}")).json()["title"] == "Лист"


# --- Stories ------------------------------------------------------------------------------


async def test_story_lifecycle_and_visibility(ctx: Ctx, roles: dict[str, ApiClient]) -> None:
    p = await ctx.person("Галина")
    base = f"{ctx.base}/stories"
    contributor, viewer, editor = roles["contributor"], roles["viewer"], roles["editor"]

    resp = await contributor.post(
        base,
        json={
            "title": "Як ми їхали до Львова",
            "body": "## 1944\n\nДовгий **шлях**…",
            "narrator": "бабуся Галина, 2019",
            "date": y(1944),
            "person_ids": [p["id"]],
            "status": "published",
        },
    )
    assert resp.status_code == 201
    story = resp.json()
    assert story["status"] == "draft"  # contributors cannot publish
    assert story["excerpt"].startswith("1944 Довгий шлях")
    assert story["can_edit"] is True
    sid = story["id"]

    assert (await viewer.get(f"{base}/{sid}")).status_code == 404  # drafts are private
    assert (await viewer.get(base)).json()["total"] == 0
    assert (
        await roles["contributor2"].patch(f"{base}/{sid}", json={"title": "x"})
    ).status_code == 404
    assert (await viewer.post(base, json={"title": "x"})).status_code == 403

    assert (await contributor.post(f"{base}/{sid}/publish")).status_code == 403
    resp = await contributor.post(f"{base}/{sid}/submit")
    assert resp.json()["status"] == "pending_review"
    assert (await contributor.post(f"{base}/{sid}/submit")).json()["code"] == "invalid_story_status"
    assert (await editor.get(f"{ctx.base}/moderation")).json() == {"suggestions": 0, "stories": 1}

    resp = await editor.post(f"{base}/{sid}/return", json={"comment": "Додайте, будь ласка, рік"})
    assert resp.json()["status"] == "draft"
    assert resp.json()["review_comment"] == "Додайте, будь ласка, рік"
    resp = await contributor.patch(f"{base}/{sid}", json={"body": "Рік 1944. Довгий шлях…"})
    assert resp.status_code == 200
    await contributor.post(f"{base}/{sid}/submit")
    resp = await editor.post(f"{base}/{sid}/publish")
    assert resp.json()["status"] == "published"

    # Published: visible to viewers, on the person page; the contributor can no longer edit.
    seen = (await viewer.get(f"{base}/{sid}")).json()
    assert seen["persons"][0]["id"] == p["id"]
    assert seen["can_edit"] is False
    page = (await viewer.get(f"{ctx.base}/persons/{p['id']}")).json()
    assert [s["title"] for s in page["stories"]] == ["Як ми їхали до Львова"]
    assert (await contributor.patch(f"{base}/{sid}", json={"title": "x"})).status_code == 403
    assert (await contributor.delete(f"{base}/{sid}")).status_code == 403
    assert (await viewer.get(base, params={"person_id": p["id"]})).json()["total"] == 1

    # History + trash.
    history = (
        await editor.get(f"{ctx.base}/history", params={"entity_type": "story", "entity_id": sid})
    ).json()
    assert history["items"][0]["action"] == "story.publish"
    assert (await editor.delete(f"{base}/{sid}")).status_code == 204
    assert (await viewer.get(f"{base}/{sid}")).status_code == 404
    await editor.post(f"{ctx.base}/trash/story/{sid}/restore")
    assert (await viewer.get(f"{base}/{sid}")).status_code == 200


async def test_editor_story_with_media(ctx: Ctx) -> None:
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (8, 8)).save(buf, "PNG")
    media = (
        await ctx.editor.post(
            f"{ctx.base}/media", files={"file": ("a.png", buf.getvalue(), "image/png")}
        )
    ).json()
    resp = await ctx.editor.post(
        f"{ctx.base}/stories",
        json={"title": "Фото з весілля", "status": "published", "media_ids": [media["id"]]},
    )
    assert resp.json()["status"] == "published"
    assert [m["id"] for m in resp.json()["media"]] == [media["id"]]
    resp = await ctx.editor.post(
        f"{ctx.base}/stories", json={"title": "x", "person_ids": [str(uuid.uuid4())]}
    )
    assert resp.json()["code"] == "person_not_found"


# --- Suggestions ----------------------------------------------------------------------


async def test_suggestions_review(ctx: Ctx, roles: dict[str, ApiClient]) -> None:
    p = await ctx.person("Іван", occupation="Коваль")
    contributor, editor = roles["contributor"], roles["editor"]
    base = f"{ctx.base}/suggestions"
    patch = {"occupation": "Коваль і столяр", "birth": {"date": y(1890)}}
    resp = await contributor.post(
        base,
        json={
            "entity_type": "person",
            "entity_id": p["id"],
            "patch": patch,
            "comment": "Зі слів тітки",
        },
    )
    assert resp.status_code == 201
    s = resp.json()
    assert s["status"] == "pending"
    assert s["current"] == {"occupation": "Коваль", "birth": None}
    assert s["entity_label"] == "Іван Коваленко"

    for bad, code in [
        ({}, "empty_suggestion"),
        ({"primary_photo_id": None}, "field_not_suggestible"),
        ({"birth": {"date": {"year": 1900, "month": 2, "day": 30}}}, "invalid_suggestion"),
    ]:
        resp = await contributor.post(
            base, json={"entity_type": "person", "entity_id": p["id"], "patch": bad}
        )
        assert resp.json()["code"] == code, bad
    assert (
        await roles["viewer"].post(
            base, json={"entity_type": "person", "entity_id": p["id"], "patch": patch}
        )
    ).status_code == 403

    # Contributors see only their own; editors see all.
    await roles["contributor2"].post(
        base,
        json={"entity_type": "person", "entity_id": p["id"], "patch": {"religion": "Православний"}},
    )
    assert len((await contributor.get(base)).json()) == 1
    assert len((await editor.get(base, params={"status": "pending"})).json()) == 2
    assert (await editor.get(f"{ctx.base}/moderation")).json()["suggestions"] == 2

    assert (await contributor.post(f"{base}/{s['id']}/approve")).status_code == 403
    resp = await editor.post(f"{base}/{s['id']}/approve", json={"comment": "Дякую!"})
    assert resp.json()["status"] == "approved"
    assert resp.json()["reviewer"]["display_name"] == "User 1"
    page = (await editor.get(f"{ctx.base}/persons/{p['id']}")).json()
    assert page["occupation"] == "Коваль і столяр"
    assert page["birth"]["date"]["year"] == 1890
    assert (await editor.post(f"{base}/{s['id']}/reject")).json()[
        "code"
    ] == "suggestion_already_reviewed"
    history = (
        await editor.get(
            f"{ctx.base}/history", params={"entity_type": "person", "entity_id": p["id"]}
        )
    ).json()
    assert (
        history["items"][0]["user_label"] == "owner@example.com"
    )  # applied by the reviewing editor

    other = (await roles["contributor2"].get(base)).json()[0]
    resp = await editor.post(f"{base}/{other['id']}/reject", json={"comment": "Немає джерела"})
    assert resp.json()["status"] == "rejected"
    assert (await editor.post(f"{base}/{uuid.uuid4()}/approve")).status_code == 404


async def test_event_suggestion(ctx: Ctx, roles: dict[str, ApiClient]) -> None:
    p = await ctx.person("Іван")
    ev = (
        await ctx.editor.post(
            f"{ctx.base}/events",
            json={"type": "residence", "participants": [{"person_id": p["id"]}]},
        )
    ).json()
    resp = await roles["contributor"].post(
        f"{ctx.base}/suggestions",
        json={"entity_type": "event", "entity_id": ev["id"], "patch": {"title": "Хутір"}},
    )
    assert resp.json()["entity_label"] == "residence"
    await roles["editor"].post(f"{ctx.base}/suggestions/{resp.json()['id']}/approve")
    assert (await ctx.editor.get(f"{ctx.base}/events/{ev['id']}")).json()["title"] == "Хутір"
    resp = await roles["contributor"].post(
        f"{ctx.base}/suggestions",
        json={"entity_type": "event", "entity_id": str(uuid.uuid4()), "patch": {"title": "x"}},
    )
    assert resp.status_code == 404


# --- Comments & questions -------------------------------------------------------------


async def test_comments(ctx: Ctx, roles: dict[str, ApiClient]) -> None:
    p = await ctx.person("Галина")
    base = f"{ctx.base}/comments"
    resp = await roles["contributor"].post(
        base, json={"entity_type": "person", "entity_id": p["id"], "body": "Пам'ятаю її пироги!"}
    )
    assert resp.status_code == 201
    c = resp.json()
    assert c["author"]["display_name"] == "Contributor"
    assert (
        await roles["viewer"].post(
            base, json={"entity_type": "person", "entity_id": p["id"], "body": "x"}
        )
    ).status_code == 403
    listing = (
        await roles["viewer"].get(base, params={"entity_type": "person", "entity_id": p["id"]})
    ).json()
    assert [x["body"] for x in listing] == ["Пам'ятаю її пироги!"]

    assert (
        await roles["contributor2"].patch(f"{base}/{c['id']}", json={"body": "x"})
    ).status_code == 403
    assert (await roles["contributor2"].delete(f"{base}/{c['id']}")).status_code == 403
    resp = await roles["contributor"].patch(
        f"{base}/{c['id']}", json={"body": "Пам'ятаю її вареники!"}
    )
    assert resp.json()["body"] == "Пам'ятаю її вареники!"
    assert (await roles["editor"].delete(f"{base}/{c['id']}")).status_code == 204  # moderation
    assert (
        await roles["viewer"].get(base, params={"entity_type": "person", "entity_id": p["id"]})
    ).json() == []
    assert (await roles["editor"].delete(f"{base}/{c['id']}")).status_code == 404

    # Comments on a draft story are as private as the story.
    draft = (
        await roles["contributor"].post(f"{ctx.base}/stories", json={"title": "Чернетка"})
    ).json()
    resp = await roles["viewer"].get(
        base, params={"entity_type": "story", "entity_id": draft["id"]}
    )
    assert resp.status_code == 404
    resp = await roles["contributor"].post(
        base, json={"entity_type": "story", "entity_id": draft["id"], "body": "нотатка"}
    )
    assert resp.status_code == 201
    resp = await roles["contributor"].post(
        base, json={"entity_type": "media", "entity_id": str(uuid.uuid4()), "body": "x"}
    )
    assert resp.json()["code"] == "comment_target_not_found"


async def test_open_questions(ctx: Ctx, roles: dict[str, ApiClient]) -> None:
    p = await ctx.person("Петро")
    base = f"{ctx.base}/questions"
    resp = await roles["contributor"].post(
        base, json={"person_id": p["id"], "question": "Де він був у 1941–1945?"}
    )
    assert resp.status_code == 201
    q = resp.json()
    assert q["status"] == "open"
    assert q["person_name"] == "Петро Коваленко"
    assert (
        await roles["viewer"].post(base, json={"person_id": p["id"], "question": "x"})
    ).status_code == 403
    resp = await roles["contributor2"].patch(
        f"{base}/{q['id']}", json={"status": "resolved", "resolution": "Архів ЦАМО"}
    )
    assert resp.json()["status"] == "resolved"
    assert resp.json()["resolved_at"]
    resp = await roles["contributor2"].patch(f"{base}/{q['id']}", json={"status": "open"})
    assert resp.json()["resolved_at"] is None
    page = (await roles["viewer"].get(f"{ctx.base}/persons/{p['id']}")).json()
    assert [x["question"] for x in page["open_questions"]] == ["Де він був у 1941–1945?"]
    assert len((await roles["viewer"].get(base, params={"status": "open"})).json()) == 1
    assert (await roles["contributor2"].delete(f"{base}/{q['id']}")).status_code == 403
    assert (await roles["contributor"].delete(f"{base}/{q['id']}")).status_code == 204
    assert (
        await roles["editor"].patch(f"{base}/{q['id']}", json={"notes": "x"})
    ).status_code == 404


# --- Data quality -----------------------------------------------------------------------


async def test_data_quality(ctx: Ctx, roles: dict[str, ApiClient]) -> None:
    full = await ctx.person("Повна", birth={"date": y(1900)})
    s = await source(ctx)
    await ctx.editor.post(
        f"{ctx.base}/citations",
        json={"source_id": s["id"], "entity_type": "event", "entity_id": full["birth"]["event_id"]},
    )
    no_birth = await ctx.person("Бездати")
    parent = await ctx.person("Батько", birth={"date": y(1950)})
    child = await ctx.person("Дитина", birth={"date": y(1940)})
    await ctx.link(parent["id"], child["id"])
    late = await ctx.person("Пізня", birth={"date": y(1900)}, death={"date": y(1950)})
    await ctx.editor.post(
        f"{ctx.base}/events",
        json={"type": "residence", "date": y(1960), "participants": [{"person_id": late["id"]}]},
    )
    await roles["contributor"].post(
        f"{ctx.base}/questions", json={"person_id": no_birth["id"], "question": "Коли народився?"}
    )

    dq = (await roles["contributor"].get(f"{ctx.base}/data-quality")).json()
    assert dq["counts"] == {
        "people": 5,
        "missing_birth": 1,
        "missing_photo": 5,
        "without_sources": 4,
        "date_problems": 2,
        "open_questions": 1,
    }
    assert [p["id"] for p in dq["missing_birth"]] == [no_birth["id"]]
    assert full["id"] not in [p["id"] for p in dq["without_sources"]]
    problems = {d["person"]["id"]: [w["code"] for w in d["warnings"]] for d in dq["date_problems"]}
    assert problems == {
        child["id"]: ["child_born_before_parent"],
        late["id"]: ["event_after_death"],
    }
    assert dq["open_questions"][0]["question"] == "Коли народився?"
    assert (await roles["viewer"].get(f"{ctx.base}/data-quality")).status_code == 403
    assert (await roles["contributor"].get(f"{ctx.base}/moderation")).status_code == 403


async def test_story_cover_and_reading_time(ctx: Ctx, session: Any, local_storage: Any) -> None:
    from app.services.genealogy import media as media_service
    from tests.test_media_api import jpeg, upload

    photo = (await upload(ctx, "wedding.jpg", jpeg())).json()
    await media_service.process_media(session, local_storage, uuid.UUID(photo["id"]))
    body = " ".join(["слово"] * 900)  # ~5 minutes
    resp = await ctx.editor.post(
        f"{ctx.base}/stories",
        json={"title": "Весілля", "body": body, "status": "published", "media_ids": [photo["id"]]},
    )
    assert resp.status_code == 201, resp.text
    listing = (await ctx.editor.get(f"{ctx.base}/stories")).json()["items"]
    story = next(s for s in listing if s["title"] == "Весілля")
    assert story["reading_minutes"] == 5
    assert story["cover_url"].startswith(
        f"/api/v1/trees/{ctx.tree.id}/media/{photo['id']}/file/thumb"
    )

    resp = await ctx.editor.post(f"{ctx.base}/stories", json={"title": "Коротко", "body": "Так."})
    assert resp.json()["reading_minutes"] == 1
    assert resp.json()["cover_url"] is None
