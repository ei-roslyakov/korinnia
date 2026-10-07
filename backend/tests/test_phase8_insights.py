"""Timeline, on this day, map, relationship calculator and statistics."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Any

import pytest

from app.core.dates import PartialDate
from app.core.enums import DatePrecision, ParentChildType
from app.models import TreeRole, User
from app.services.genealogy.kinship import FamilyIndex, find
from app.services.genealogy.stats import age, count_names, generations
from tests.conftest import ApiClient
from tests.helpers import Ctx, y

# --- Kinship engine (pure) ----------------------------------------------------------------


class Family:
    """A tiny in-memory family graph addressed by names."""

    def __init__(self) -> None:
        self.ids: dict[str, uuid.UUID] = {}
        self.idx = FamilyIndex()

    def __getitem__(self, name: str) -> uuid.UUID:
        return self.ids.setdefault(name, uuid.uuid4())

    def child(
        self, child: str, *parents: str, type_: ParentChildType = ParentChildType.biological
    ) -> Family:
        for p in parents:
            self.idx.parents.setdefault(self[child], []).append((self[p], type_))
            self.idx.children.setdefault(self[p], []).append(self[child])
        return self

    def couple(self, a: str, b: str) -> Family:
        self.idx.partners.setdefault(self[a], []).append(self[b])
        self.idx.partners.setdefault(self[b], []).append(self[a])
        return self

    def rel(self, a: str, b: str) -> tuple[str, int | None, int | None, bool]:
        f = find(self.idx, self[a], self[b])
        r = f.blood
        return f.kind, r.up if r else None, r.down if r else None, r.half if r else False


@pytest.fixture
def fam() -> Family:
    """Grandparents gp1+gp2 → father, uncle; father+mother → me, sister; uncle+aunt →
    cousin → cousin_kid; me + wife → son; gp1 + gp_second → half_uncle."""
    f = Family()
    f.couple("gp1", "gp2").couple("father", "mother").couple("uncle", "aunt")
    f.couple("me", "wife").couple("wife_father", "wife_mother")
    f.child("father", "gp1", "gp2").child("uncle", "gp1", "gp2")
    f.child("me", "father", "mother").child("sister", "father", "mother")
    f.child("cousin", "uncle", "aunt").child("cousin_kid", "cousin")
    f.child("son", "me", "wife").child("wife", "wife_father", "wife_mother")
    f.child("wife_brother", "wife_father", "wife_mother")
    f.couple("gp1", "gp_second").child("half_uncle", "gp1", "gp_second")
    f.couple("sister", "sister_husband")
    return f


@pytest.mark.parametrize(
    ("b", "expected"),
    [
        ("me", ("same", None, None, False)),
        ("father", ("blood", 1, 0, False)),
        ("gp2", ("blood", 2, 0, False)),
        ("son", ("blood", 0, 1, False)),
        ("sister", ("blood", 1, 1, False)),
        ("uncle", ("blood", 2, 1, False)),
        ("half_uncle", ("blood", 2, 1, True)),
        ("cousin", ("blood", 2, 2, False)),
        ("cousin_kid", ("blood", 2, 3, False)),
        ("wife", ("partner", None, None, False)),
        ("wife_father", ("in_law", 1, 0, False)),  # partner_relative: wife → her father
        ("wife_brother", ("in_law", 1, 1, False)),
        ("sister_husband", ("in_law", 1, 1, False)),  # relative_partner: me → sister
        ("aunt", ("in_law", 2, 1, False)),
    ],
)
def test_kinship_cases(fam: Family, b: str, expected: tuple[Any, ...]) -> None:
    assert fam.rel("me", b) == expected


def test_kinship_details(fam: Family) -> None:
    f = find(fam.idx, fam["me"], fam["cousin"])
    assert f.blood is not None
    assert set(f.blood.common) == {fam["gp1"], fam["gp2"]}
    assert f.path[0] == fam["me"]
    assert f.path[-1] == fam["cousin"]
    assert len(f.path) == 5

    in_law = find(fam.idx, fam["me"], fam["wife_father"])
    assert (in_law.side, in_law.via) == ("partner_relative", fam["wife"])
    assert in_law.path == [fam["me"], fam["wife"], fam["wife_father"]]
    sister_husband = find(fam.idx, fam["me"], fam["sister_husband"])
    assert (sister_husband.side, sister_husband.via) == ("relative_partner", fam["sister"])

    # The wife's brother's partner: only a longer chain.
    fam.couple("wife_brother", "wb_wife")
    distant = find(fam.idx, fam["me"], fam["wb_wife"])
    assert distant.kind == "distant"
    assert distant.path == [
        fam["me"],
        fam["wife"],
        fam["wife_father"],
        fam["wife_brother"],
        fam["wb_wife"],
    ]
    assert find(fam.idx, fam["me"], fam["stranger"]).kind == "none"


def test_kinship_half_needs_two_known_parents_and_non_biological() -> None:
    f = Family().child("a", "p").child("b", "p")  # second parents unknown → not "half"
    assert f.rel("a", "b") == ("blood", 1, 1, False)
    g = Family().child("kid", "mum").child("adopted", "mum", type_=ParentChildType.adoptive)
    r = find(g.idx, g["kid"], g["adopted"]).blood
    assert r is not None
    assert r.non_biological
    assert find(g.idx, g["kid"], g["mum"]).blood.non_biological is False  # type: ignore[union-attr]


def test_kinship_pedigree_collapse_and_cycles() -> None:
    # Cousins who married: their child descends from gp twice; the closest line wins.
    f = Family().child("x", "gp").child("y", "gp").child("cx", "x").child("cy", "y")
    f.child("kid", "cx", "cy")
    assert f.rel("kid", "gp") == ("blood", 3, 0, False)
    # A cycle in bad data must not hang.
    c = Family().child("a", "b").child("b", "a")
    assert c.rel("a", "b")[0] == "blood"
    assert generations(c.idx, [c["a"], c["b"]]) >= 1


# --- Statistics helpers (pure) ------------------------------------------------------------


def test_age_and_names() -> None:
    exact = DatePrecision.exact
    b = PartialDate(1900, 6, 15, exact)
    assert age(b, PartialDate(1980, 6, 14, exact)) == 79
    assert age(b, PartialDate(1980, None, None, DatePrecision.year)) == 80
    assert age(PartialDate(1900, None, None, DatePrecision.approx), PartialDate(1980)) is None
    assert age(b, None) is None
    assert age(b, PartialDate(1700, None, None, DatePrecision.year)) is None  # implausible
    p1, p2, p3 = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    names = count_names({p1: {"Коваленко"}, p2: {"Kovalenko", "Бойко"}, p3: {"Коваленко"}})
    assert names[0].name == "Коваленко"
    assert names[0].count == 3
    assert names[0].variants == ["Kovalenko"]
    assert [n.name for n in names] == ["Коваленко", "Бойко"]
    assert generations(FamilyIndex(), []) == 0


# --- API ----------------------------------------------------------------------------------


async def partnership(ctx: Ctx, a: str, b: str, **extra: Any) -> Any:
    resp = await ctx.editor.post(
        f"{ctx.base}/partnerships", json={"person_a_id": a, "person_b_id": b, **extra}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def event(ctx: Ctx, type_: str, who: list[str], **extra: Any) -> Any:
    resp = await ctx.editor.post(
        f"{ctx.base}/events",
        json={"type": type_, "participants": [{"person_id": p} for p in who], **extra},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.fixture
async def family(ctx: Ctx) -> dict[str, Any]:
    poltava = await ctx.place("Полтава", latitude="49.588300", longitude="34.551400")
    lviv = await ctx.place("Львів", latitude="49.839700", longitude="24.029700")
    village = await ctx.place("Хутір без координат")
    ivan = await ctx.person(
        "Іван",
        gender="male",
        birth={"date": y(1900, month=3, day=12, precision="exact"), "place_id": poltava["id"]},
        death={"date": y(1975, month=10, day=7, precision="exact"), "place_id": lviv["id"]},
    )
    maria = await ctx.person(
        "Марія",
        "Бойко",
        gender="female",
        birth={"date": y(1904, month=2, day=29, precision="exact"), "place_id": village["id"]},
        death={"date": y(1990)},
    )
    petro = await ctx.person(
        "Петро", gender="male", birth={"date": y(1930, month=10, day=8, precision="exact")}
    )
    olha = await ctx.person("Ольга", "Kovalenko", gender="female", birth={"date": y(1933)})
    for kid in (petro, olha):
        await ctx.link(ivan["id"], kid["id"])
        await ctx.link(maria["id"], kid["id"])
    await partnership(
        ctx,
        ivan["id"],
        maria["id"],
        start_date=y(1928, month=10, day=7, precision="exact"),
        place_id=poltava["id"],
    )
    await event(
        ctx,
        "burial",
        [ivan["id"]],
        date=y(1975, month=10, day=10, precision="exact"),
        place_id=lviv["id"],
        cemetery_name="Личаківський цвинтар",
        latitude="49.831000",
        longitude="24.056000",
    )
    await event(ctx, "residence", [petro["id"]], title="Без дати", place_id=lviv["id"])
    return {"ivan": ivan, "maria": maria, "petro": petro, "olha": olha}


async def test_timeline(ctx: Ctx, family: dict[str, Any]) -> None:
    resp = await ctx.editor.get(f"{ctx.base}/timeline")
    assert resp.status_code == 200, resp.text
    page = resp.json()
    types = [(f["type"], f["date"]["year"]) for f in page["items"]]
    assert types[:3] == [("birth", 1900), ("birth", 1904), ("marriage", 1928)]
    assert types[-1] == ("death", 1990)
    assert page["undated"] == 1
    assert page["total"] == len(types) == 8
    marriage = page["items"][2]
    assert marriage["kind"] == "partnership_start"
    assert marriage["place"]["name"] == "Полтава"
    assert {p["display_name"] for p in marriage["persons"]} == {"Іван Коваленко", "Марія Бойко"}

    # Filters: type, person, years, paging.
    got = (await ctx.editor.get(f"{ctx.base}/timeline?type=death&type=burial")).json()
    assert [f["type"] for f in got["items"]] == ["death", "burial", "death"]
    pid = family["petro"]["id"]
    got = (await ctx.editor.get(f"{ctx.base}/timeline?person_id={pid}")).json()
    assert [f["type"] for f in got["items"]] == ["birth"]
    assert got["undated"] == 1
    got = (await ctx.editor.get(f"{ctx.base}/timeline?from_year=1929&to_year=1975")).json()
    assert [f["date"]["year"] for f in got["items"]] == [1930, 1933, 1975, 1975]
    got = (await ctx.editor.get(f"{ctx.base}/timeline?limit=2&offset=2")).json()
    assert [f["type"] for f in got["items"]] == ["marriage", "birth"]
    assert got["total"] == 8

    # A marriage event for the same couple replaces the partnership fact.
    ivan, maria = family["ivan"]["id"], family["maria"]["id"]
    await event(ctx, "marriage", [ivan, maria], date=y(1928, month=10, day=7, precision="exact"))
    got = (await ctx.editor.get(f"{ctx.base}/timeline?type=marriage")).json()
    assert [f["kind"] for f in got["items"]] == ["event"]


async def test_partnership_end_facts(ctx: Ctx) -> None:
    a, b = await ctx.person("А"), await ctx.person("Б")
    c, d = await ctx.person("В"), await ctx.person("Г")
    await partnership(
        ctx, a["id"], b["id"], type="civil_union", end_date=y(1990), end_reason="divorce"
    )
    await partnership(ctx, c["id"], d["id"], end_date=y(1991), end_reason="death")
    await partnership(ctx, a["id"], c["id"], end_date=y(1992), end_reason="other")
    got = (await ctx.editor.get(f"{ctx.base}/timeline")).json()
    assert [(f["kind"], f["type"]) for f in got["items"]] == [
        ("partnership_end", "divorce"),
        ("partnership_end", "partnership_end"),
    ]


async def test_on_this_day(ctx: Ctx, family: dict[str, Any]) -> None:
    resp = await ctx.editor.get(f"{ctx.base}/on-this-day?date=2025-10-07")
    assert resp.status_code == 200, resp.text
    items = resp.json()["items"]
    # Ivan's death (50 years) and the wedding (97 years) — not the year-only facts.
    assert [(i["fact"]["type"], i["years"]) for i in items] == [("marriage", 97), ("death", 50)]

    week = (await ctx.editor.get(f"{ctx.base}/on-this-day?date=2025-10-07&days=7")).json()
    assert [(i["on"], i["fact"]["type"]) for i in week["items"]] == [
        ("2025-10-07", "marriage"),
        ("2025-10-07", "death"),
        ("2025-10-08", "birth"),
        ("2025-10-10", "burial"),
    ]
    # 29 February falls on the 28th in common years; windows can span New Year.
    feb = (await ctx.editor.get(f"{ctx.base}/on-this-day?date=2025-02-28")).json()
    assert [(i["fact"]["type"], i["years"]) for i in feb["items"]] == [("birth", 121)]
    leap = (await ctx.editor.get(f"{ctx.base}/on-this-day?date=2028-02-28")).json()
    assert leap["items"] == []
    nye = (await ctx.editor.get(f"{ctx.base}/on-this-day?date=2025-12-31&days=31")).json()
    assert [i["on"] for i in nye["items"]] == []
    nye = (await ctx.editor.get(f"{ctx.base}/on-this-day?date=2025-12-20&days=31")).json()
    assert nye["days"] == 31
    assert (await ctx.editor.get(f"{ctx.base}/on-this-day?days=32")).status_code == 422
    assert (await ctx.editor.get(f"{ctx.base}/on-this-day")).status_code == 200


async def test_map(ctx: Ctx, family: dict[str, Any]) -> None:
    resp = await ctx.editor.get(f"{ctx.base}/map")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    by_label = {p["label"]: [f["type"] for f in p["facts"]] for p in data["points"]}
    assert by_label == {
        "Полтава": ["birth", "marriage"],
        "Львів": ["death", "residence"],
        "Личаківський цвинтар": ["burial"],
    }
    assert data["unplaced"] == 1
    assert [p["name"] for p in data["places_without_coordinates"]] == ["Хутір без координат"]

    pid = family["petro"]["id"]
    mine = (await ctx.editor.get(f"{ctx.base}/map?person_id={pid}")).json()
    assert [p["label"] for p in mine["points"]] == ["Львів"]


async def test_relationship_api(
    ctx: Ctx,
    family: dict[str, Any],
    make_user: Callable[..., Awaitable[User]],
    make_client: Callable[[], Awaitable[ApiClient]],
    add_member: Callable[..., Awaitable[Any]],
) -> None:
    viewer = await make_user("viewer@example.com")
    await add_member(ctx.tree, viewer, TreeRole.viewer)
    client = await make_client()
    await client.login(viewer.email)

    petro, olha, ivan = family["petro"]["id"], family["olha"]["id"], family["ivan"]["id"]
    resp = await client.get(f"{ctx.base}/relationship?a={petro}&b={olha}")
    assert resp.status_code == 200, resp.text
    r = resp.json()
    assert (r["kind"], r["up"], r["down"], r["half"]) == ("blood", 1, 1, False)
    assert {p["display_name"] for p in r["common_ancestors"]} == {"Іван Коваленко", "Марія Бойко"}
    assert [s["edge"] for s in r["path"]] == [None, "parent", "child"]
    assert r["b"]["display_name"] == "Ольга Kovalenko"

    r = (await client.get(f"{ctx.base}/relationship?a={ivan}&b={family['maria']['id']}")).json()
    assert r["kind"] == "partner"
    assert [s["edge"] for s in r["path"]] == [None, "partner"]

    stranger = await ctx.person("Чужий")
    r = (await client.get(f"{ctx.base}/relationship?a={ivan}&b={stranger['id']}")).json()
    assert r["kind"] == "none"
    assert r["path"] == []

    resp = await client.get(f"{ctx.base}/relationship?a={ivan}&b={uuid.uuid4()}")
    assert resp.status_code == 404


async def test_stats(ctx: Ctx, family: dict[str, Any]) -> None:
    resp = await ctx.editor.get(f"{ctx.base}/stats")
    assert resp.status_code == 200, resp.text
    s = resp.json()
    assert (s["persons"], s["male"], s["female"], s["other_gender"]) == (4, 2, 2, 0)
    assert s["generations"] == 2
    assert s["partnerships"] == 1
    assert (s["places"], s["events"]) == (3, 8)  # 4 births, 2 deaths, burial, residence
    assert (s["earliest_year"], s["latest_year"]) == (1900, 1990)
    assert s["oldest_ancestor"]["person"]["display_name"] == "Іван Коваленко"
    assert s["longest_lived"]["years"] == 86  # Maria 1904 → 1990
    assert s["average_lifespan"] == 80.5
    assert s["lifespan_sample"] == 2
    assert s["surnames"][0] == {"name": "Коваленко", "count": 3, "variants": ["Kovalenko"]}
    assert s["surnames"][1]["name"] == "Бойко"
    assert {d["decade"]: (d["births"], d["deaths"]) for d in s["by_decade"]} == {
        1900: (2, 0),
        1930: (2, 0),
        1970: (0, 1),
        1990: (0, 1),
    }
    assert s["living"] + s["deceased"] == 4


async def test_insights_need_membership(
    ctx: Ctx,
    make_user: Callable[..., Awaitable[User]],
    make_client: Callable[[], Awaitable[ApiClient]],
) -> None:
    await make_user("outsider@example.com")
    client = await make_client()
    await client.login("outsider@example.com")
    for path in ("timeline", "on-this-day", "map", "stats"):
        assert (await client.get(f"{ctx.base}/{path}")).status_code == 404
