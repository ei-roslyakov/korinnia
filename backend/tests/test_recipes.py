"""Family recipes and traditions are stories with a kind (D117)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Tree, TreeMembership, TreeRole, User
from app.schemas.stories import Recipe, StoryCreate
from tests.conftest import ApiClient
from tests.helpers import Ctx

RECIPE: dict[str, Any] = {
    "servings": 6,
    "prep_minutes": 60,
    "cook_minutes": 15,
    "ingredients": [{"amount": "500 г", "item": "борошно"}, {"item": "вишні"}],
    "steps": ["Замісити тісто.", "  ", "Зліпити вареники.", "Зварити."],
}


# --- Validation -----------------------------------------------------------------------------


def test_recipe_schema() -> None:
    recipe = Recipe.model_validate(RECIPE)
    assert recipe.steps == ["Замісити тісто.", "Зліпити вареники.", "Зварити."]  # blanks dropped
    assert recipe.ingredients[1].amount is None
    for bad in (
        {"servings": 0},
        {"prep_minutes": -1},
        {"ingredients": [{"amount": "1"}]},  # an ingredient needs an item
        {"ingredients": [{"item": ""}]},
        {"steps": ["x" * 5001]},
    ):
        with pytest.raises(ValidationError):
            Recipe.model_validate(bad)
    with pytest.raises(ValidationError, match="only a recipe"):
        StoryCreate.model_validate({"title": "x", "kind": "story", "recipe": RECIPE})
    tradition = StoryCreate.model_validate(
        {"title": "Свят-вечір", "kind": "tradition", "occasion": "Святий вечір"}
    )
    assert tradition.recipe is None


# --- API ------------------------------------------------------------------------------------


async def test_create_filter_search_and_publish_a_recipe(
    ctx: Ctx,
    make_user: Callable[..., Awaitable[User]],
    make_client: Callable[[], Awaitable[ApiClient]],
    add_member: Callable[..., Awaitable[TreeMembership]],
    session: AsyncSession,
) -> None:
    valentyna = await ctx.person("Валентина", "Литвин")
    user = await make_user("contributor@example.com")
    await add_member(await session.get(Tree, ctx.tree.id), user, TreeRole.contributor)
    contributor = await make_client()
    await contributor.login("contributor@example.com")

    created = await contributor.post(
        f"{ctx.base}/stories",
        json={
            "title": "Вареники з вишнями",
            "kind": "recipe",
            "occasion": "Літо",
            "narrator": "Валентина",
            "body": "Щочервня вся родина ліпила вареники.",
            "recipe": RECIPE,
            "person_ids": [valentyna["id"]],
            "status": "published",
        },
    )
    assert created.status_code == 201, created.text
    recipe = created.json()
    assert (recipe["kind"], recipe["occasion"], recipe["status"]) == ("recipe", "Літо", "draft")
    assert len(recipe["recipe"]["ingredients"]) == 2
    assert len(recipe["recipe"]["steps"]) == 3

    tradition = await ctx.editor.post(
        f"{ctx.base}/stories",
        json={
            "title": "Свят-вечір",
            "kind": "tradition",
            "occasion": "Святий вечір",
            "body": "Дванадцять страв.",
            "person_ids": [valentyna["id"]],
            "status": "published",
        },
    )
    assert tradition.status_code == 201
    plain = await ctx.editor.post(
        f"{ctx.base}/stories", json={"title": "Як познайомилися", "status": "published"}
    )
    assert plain.json()["kind"] == "story"
    bad = await ctx.editor.post(
        f"{ctx.base}/stories", json={"title": "x", "kind": "tradition", "recipe": RECIPE}
    )
    assert bad.status_code == 422

    # Contributor submits, editor publishes: the same review as any story.
    assert (await contributor.post(f"{ctx.base}/stories/{recipe['id']}/submit")).status_code == 200
    published = await ctx.editor.post(f"{ctx.base}/stories/{recipe['id']}/publish")
    assert published.json()["status"] == "published"

    async def titles(**params: Any) -> list[str]:
        resp = await ctx.editor.get(f"{ctx.base}/stories", params=params)
        assert resp.status_code == 200, resp.text
        return sorted(s["title"] for s in resp.json()["items"])

    assert await titles(kind=["recipe", "tradition"]) == ["Вареники з вишнями", "Свят-вечір"]
    assert await titles(kind="story") == ["Як познайомилися"]
    assert await titles(q="вишні") == ["Вареники з вишнями"]  # an ingredient
    assert await titles(q="святий") == ["Свят-вечір"]  # the occasion, any case
    assert await titles(q="борошно літо") == ["Вареники з вишнями"]  # every word must match
    assert await titles(q="пельмені") == []

    page = (await ctx.editor.get(f"{ctx.base}/persons/{valentyna['id']}")).json()
    assert {(s["title"], s["kind"]) for s in page["stories"]} == {
        ("Вареники з вишнями", "recipe"),
        ("Свят-вечір", "tradition"),
    }

    # A recipe turned into a story loses its ingredients and steps; a story cannot get them.
    changed = await ctx.editor.patch(f"{ctx.base}/stories/{recipe['id']}", json={"kind": "story"})
    assert changed.json()["recipe"] is None
    refused = await ctx.editor.patch(f"{ctx.base}/stories/{recipe['id']}", json={"recipe": RECIPE})
    assert (refused.status_code, refused.json()["code"]) == (400, "recipe_only_for_recipes")
    # …and the history can bring the recipe back.
    history = (
        await ctx.editor.get(
            f"{ctx.base}/history", params={"entity_type": "story", "entity_id": recipe["id"]}
        )
    ).json()["items"]
    publish = next(h for h in history if h["action"] == "story.publish")
    restored = await ctx.editor.post(f"{ctx.base}/history/{publish['id']}/restore")
    assert restored.status_code == 200, restored.text
    again = (await ctx.editor.get(f"{ctx.base}/stories/{recipe['id']}")).json()
    assert again["kind"] == "recipe"
    assert len(again["recipe"]["steps"]) == 3
