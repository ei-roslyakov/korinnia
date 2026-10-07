"""Role-based access matrix (acceptance criteria).

- viewer: read only
- contributor: read (suggestions come in phase 7)
- editor: full content edit (phase 3+) but cannot manage members or users
- admin: editor + manage the tree's members, delete the tree
- outsider: cannot even see that the tree exists (404)
- superadmin: everything, including users, tree creation and restoring deleted trees
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import pytest

from app.models import Tree, TreeRole, User
from tests.conftest import ApiClient

ROLES = ["outsider", "viewer", "contributor", "editor", "admin", "superadmin"]


@dataclass
class World:
    tree: Tree
    users: dict[str, User]
    member: User  # an extra viewer, target for member management calls


@pytest.fixture
async def world(
    make_user: Callable[..., Awaitable[User]],
    make_tree: Callable[..., Awaitable[Tree]],
    add_member: Callable[..., Awaitable[Any]],
) -> World:
    owner = await make_user("owner@example.com")
    tree = await make_tree(owner)
    users = {"admin": owner}
    users["superadmin"] = await make_user("super@example.com", is_superadmin=True)
    users["outsider"] = await make_user("outsider@example.com")
    for role in ("viewer", "contributor", "editor"):
        users[role] = await make_user(f"{role}@example.com")
        await add_member(tree, users[role], TreeRole(role))
    member = await make_user("member@example.com")
    await add_member(tree, member, TreeRole.viewer)
    return World(tree=tree, users=users, member=member)


Call = Callable[[ApiClient, World], Awaitable[Any]]

CASES: dict[str, tuple[Call, dict[str, int]]] = {
    "read tree": (
        lambda c, w: c.get(f"/api/v1/trees/{w.tree.id}"),
        {
            "outsider": 404,
            "viewer": 200,
            "contributor": 200,
            "editor": 200,
            "admin": 200,
            "superadmin": 200,
        },
    ),
    "rename tree": (
        lambda c, w: c.patch(f"/api/v1/trees/{w.tree.id}", json={"name": "New name"}),
        {
            "outsider": 404,
            "viewer": 403,
            "contributor": 403,
            "editor": 403,
            "admin": 200,
            "superadmin": 200,
        },
    ),
    "list members": (
        lambda c, w: c.get(f"/api/v1/trees/{w.tree.id}/members"),
        {
            "outsider": 404,
            "viewer": 403,
            "contributor": 403,
            "editor": 403,
            "admin": 200,
            "superadmin": 200,
        },
    ),
    "invite member": (
        lambda c, w: c.post(
            f"/api/v1/trees/{w.tree.id}/members",
            json={"email": "new@example.com", "role": "viewer"},
        ),
        {
            "outsider": 404,
            "viewer": 403,
            "contributor": 403,
            "editor": 403,
            "admin": 201,
            "superadmin": 201,
        },
    ),
    "change member role": (
        lambda c, w: c.patch(
            f"/api/v1/trees/{w.tree.id}/members/{w.member.id}", json={"role": "editor"}
        ),
        {
            "outsider": 404,
            "viewer": 403,
            "contributor": 403,
            "editor": 403,
            "admin": 200,
            "superadmin": 200,
        },
    ),
    "remove member": (
        lambda c, w: c.delete(f"/api/v1/trees/{w.tree.id}/members/{w.member.id}"),
        {
            "outsider": 404,
            "viewer": 403,
            "contributor": 403,
            "editor": 403,
            "admin": 204,
            "superadmin": 204,
        },
    ),
    "tree audit log": (
        lambda c, w: c.get(f"/api/v1/trees/{w.tree.id}/audit-log"),
        {
            "outsider": 404,
            "viewer": 403,
            "contributor": 403,
            "editor": 403,
            "admin": 200,
            "superadmin": 200,
        },
    ),
    "delete tree": (
        lambda c, w: c.delete(f"/api/v1/trees/{w.tree.id}"),
        {
            "outsider": 404,
            "viewer": 403,
            "contributor": 403,
            "editor": 403,
            "admin": 204,
            "superadmin": 204,
        },
    ),
    "create tree": (
        lambda c, w: c.post("/api/v1/trees", json={"name": "Another"}),
        {
            "outsider": 403,
            "viewer": 403,
            "contributor": 403,
            "editor": 403,
            "admin": 403,
            "superadmin": 201,
        },
    ),
    "list users": (
        lambda c, w: c.get("/api/v1/admin/users"),
        {
            "outsider": 403,
            "viewer": 403,
            "contributor": 403,
            "editor": 403,
            "admin": 403,
            "superadmin": 200,
        },
    ),
    "create user": (
        lambda c, w: c.post(
            "/api/v1/admin/users",
            json={"email": "x@example.com", "display_name": "X", "password": "long-password-1"},
        ),
        {
            "outsider": 403,
            "viewer": 403,
            "contributor": 403,
            "editor": 403,
            "admin": 403,
            "superadmin": 201,
        },
    ),
    "global audit log": (
        lambda c, w: c.get("/api/v1/admin/audit-log"),
        {
            "outsider": 403,
            "viewer": 403,
            "contributor": 403,
            "editor": 403,
            "admin": 403,
            "superadmin": 200,
        },
    ),
}


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("case", list(CASES))
async def test_access_matrix(
    case: str, role: str, world: World, make_client: Callable[[], Awaitable[ApiClient]]
) -> None:
    call, expected = CASES[case]
    client = await make_client()
    await client.login(world.users[role].email)
    resp = await call(client, world)
    assert resp.status_code == expected[role], f"{case} as {role}: {resp.text}"


async def test_anonymous_gets_401(world: World, client: ApiClient) -> None:
    for url in (f"/api/v1/trees/{world.tree.id}", "/api/v1/trees", "/api/v1/admin/users"):
        assert (await client.get(url)).status_code == 401


async def test_unknown_tree_is_404_even_for_superadmin(
    world: World, make_client: Callable[[], Awaitable[ApiClient]]
) -> None:
    client = await make_client()
    await client.login("super@example.com")
    assert (await client.get(f"/api/v1/trees/{uuid.uuid4()}")).status_code == 404


async def test_tree_list_shows_only_own_trees(
    world: World,
    make_client: Callable[[], Awaitable[ApiClient]],
    make_tree: Callable[..., Awaitable[Tree]],
) -> None:
    await make_tree(world.users["superadmin"], name="Other family")
    viewer = await make_client()
    await viewer.login("viewer@example.com")
    trees = (await viewer.get("/api/v1/trees")).json()
    assert [(t["name"], t["my_role"]) for t in trees] == [("Rosliakov family", "viewer")]
    outsider = await make_client()
    await outsider.login("outsider@example.com")
    assert (await outsider.get("/api/v1/trees")).json() == []
    sa = await make_client()
    await sa.login("super@example.com")
    assert len((await sa.get("/api/v1/trees")).json()) == 2
