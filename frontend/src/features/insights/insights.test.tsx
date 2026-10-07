import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "@/App";
import i18n from "@/i18n";
import type { Fact, Relationship, TreeStats } from "@/lib/genealogy";
import { halyna, smallGraph, summary } from "@/test/fixtures";
import { json, ME, mockApi, type Handler } from "@/test/mockApi";
import { renderWithProviders } from "@/test/render";

vi.mock("@/features/tree/canvas/TreeCanvas", () => ({ TreeCanvas: () => <div /> }));
vi.mock("@/features/builder/MapPicker", () => ({ MapPicker: () => <div /> }));
// Leaflet needs a real layout engine; a chainable stub is enough for the page logic.
vi.mock("leaflet", () => {
  const stub: object = new Proxy(() => stub, {
    get: (_, key) => (key === "then" ? undefined : () => stub),
  });
  return { default: stub };
});

beforeEach(async () => {
  await i18n.changeLanguage("uk");
  document.cookie = "korinnia_csrf=x; path=/";
});
afterEach(() => vi.unstubAllGlobals());

const date = (year: number, month: number | null = null, day: number | null = null) => ({
  year,
  month,
  day,
  precision: day ? "exact" : month ? "month" : "year",
  end_year: null,
  end_month: null,
  end_day: null,
  phrase: null,
  text: String(year),
  sort: `${year}-01-01`,
});

const fact = (id: string, type: string, year: number, extra: Partial<Fact> = {}): Fact => ({
  kind: "event",
  id,
  type,
  title: null,
  date: date(year) as Fact["date"],
  place: null,
  latitude: null,
  longitude: null,
  cemetery_name: null,
  persons: [{ id: "p2", display_name: "Галина Коваленко", role: "principal" }],
  ...extra,
});

function api(extra: Record<string, Handler> = {}, role = "viewer") {
  return mockApi({
    "GET /api/v1/auth/me": () => json(ME),
    "GET /api/v1/trees/t1": () =>
      json({ id: "t1", name: "Родина", description: null, my_role: role }),
    "GET /api/v1/trees/t1/graph": () => json(smallGraph),
    "GET /api/v1/trees/t1/persons/p2": () => json(halyna),
    ...extra,
  });
}

describe("tree navigation", () => {
  it("links the new views from the tree toolbar", async () => {
    api();
    renderWithProviders(<App />, { route: "/trees/t1" });
    const nav = await screen.findByRole("navigation", { name: "Розділи родоводу" });
    for (const [name, href] of [
      ["Хронологія", "/trees/t1/timeline"],
      ["Карта", "/trees/t1/map"],
      ["Цього дня", "/trees/t1/on-this-day"],
      ["Спорідненість", "/trees/t1/relationship"],
      ["Статистика", "/trees/t1/stats"],
    ]) {
      expect(within(nav).getByRole("link", { name })).toHaveAttribute("href", href);
    }
    expect(within(nav).queryByRole("link", { name: "Учасники" })).not.toBeInTheDocument();
  });

  it("links the person to the calculator, map and timeline", async () => {
    api();
    renderWithProviders(<App />, { route: "/trees/t1/people/p2" });
    expect(await screen.findByRole("link", { name: "Спорідненість" })).toHaveAttribute(
      "href",
      "/trees/t1/relationship?a=p2",
    );
    expect(screen.getByRole("link", { name: "На карті" })).toHaveAttribute(
      "href",
      "/trees/t1/map?person=p2",
    );
  });
});

describe("timeline", () => {
  it("groups facts by decade, filters by category and loads more", async () => {
    const calls: string[] = [];
    api({
      "GET /api/v1/trees/t1/timeline": ({ url }) => {
        calls.push(url);
        const offset = Number(new URL(url, "http://x").searchParams.get("offset"));
        const items =
          offset === 0
            ? [
                fact("e1", "birth", 1923),
                fact("m1", "marriage", 1928, {
                  kind: "partnership_start",
                  persons: [
                    { id: "p1", display_name: "Іван", role: "principal" },
                    { id: "p2", display_name: "Галина", role: "principal" },
                  ],
                }),
              ]
            : [fact("e2", "death", 1990)];
        return json({ items, total: 3, limit: 100, offset, undated: 2 });
      },
    });
    renderWithProviders(<App />, { route: "/trees/t1/timeline" });
    expect(await screen.findByRole("heading", { name: "1920-ті" })).toBeInTheDocument();
    expect(screen.getByText("Шлюб")).toBeInTheDocument();
    expect(screen.getByText("Показано 2 з 3")).toBeInTheDocument();
    expect(screen.getByText("2 події без дати не показано.")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Показати ще" }));
    expect(await screen.findByRole("heading", { name: "1990-ті" })).toBeInTheDocument();
    expect(calls.at(-1)).toContain("offset=2");

    await userEvent.click(screen.getByRole("button", { name: "Смерть і поховання" }));
    expect(calls.at(-1)).toContain("type=death&type=burial");
  });
});

describe("on this day", () => {
  it("lists anniversaries with how long ago they were", async () => {
    let asked = "";
    api({
      "GET /api/v1/trees/t1/on-this-day": ({ url }) => {
        asked = url;
        return json({
          start: "2025-10-07",
          days: 7,
          items: [{ on: "2025-10-08", years: 102, fact: fact("e1", "birth", 1923) }],
        });
      },
    });
    renderWithProviders(<App />, { route: "/trees/t1/on-this-day?date=2025-10-07&days=7" });
    expect(await screen.findByText("102 роки тому")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /8 жовтня/ })).toBeInTheDocument();
    expect(asked).toContain("date=2025-10-07");
    expect(asked).toContain("days=7");
  });
});

describe("relationship calculator", () => {
  it("shows the kinship term, common ancestors and the path", async () => {
    const a = summary("p2", "Галина Коваленко");
    const b = summary("p9", "Олена Ткачук");
    const gp = summary("p5", "Степан Коваленко", { gender: "male" });
    const result: Relationship = {
      a,
      b,
      kind: "blood",
      up: 2,
      down: 2,
      half: false,
      non_biological: false,
      side: null,
      via: null,
      common_ancestors: [gp],
      path: [
        { person: a, edge: null },
        { person: summary("p3", "Петро"), edge: "parent" },
        { person: gp, edge: "parent" },
        { person: summary("p4", "Іван"), edge: "child" },
        { person: b, edge: "child" },
      ],
    };
    api({
      "GET /api/v1/trees/t1/relationship": () => json(result),
      "GET /api/v1/trees/t1/persons/p9": () =>
        json({ ...halyna, id: "p9", display_name: "Олена Ткачук" }),
    });
    renderWithProviders(<App />, { route: "/trees/t1/relationship?a=p2&b=p9" });
    expect(await screen.findByTestId("kinship-term")).toHaveTextContent("двоюрідна сестра");
    expect(screen.getByText("Найближчі спільні предки")).toBeInTheDocument();
    const path = screen.getByRole("list", { name: "Шлях у дереві" });
    expect(within(path).getAllByRole("listitem")).toHaveLength(5);
    expect(within(path).getAllByLabelText("батько або мати")).toHaveLength(2);

    await userEvent.click(screen.getByRole("button", { name: "Поміняти місцями" }));
    expect(await screen.findByTestId("kinship-term")).toBeInTheDocument();
  });

  it("asks for two people first", async () => {
    api();
    renderWithProviders(<App />, { route: "/trees/t1/relationship" });
    expect(
      await screen.findByText("Оберіть двох людей, щоб дізнатися, як вони пов'язані."),
    ).toBeInTheDocument();
    expect(screen.getAllByRole("combobox", { name: "Знайти людину…" })).toHaveLength(2);
  });
});

describe("statistics", () => {
  it("shows figures, notable people, surnames and decades", async () => {
    const stats: TreeStats = {
      persons: 25,
      male: 12,
      female: 13,
      other_gender: 0,
      living: 6,
      deceased: 19,
      generations: 5,
      partnerships: 9,
      places: 8,
      events: 60,
      media: 4,
      sources: 2,
      stories: 1,
      earliest_year: 1862,
      latest_year: 1998,
      oldest_ancestor: { person: summary("p5", "Степан Коваленко"), years: null },
      longest_lived: { person: summary("p6", "Параска Коваленко"), years: 74 },
      average_lifespan: 68.5,
      lifespan_sample: 11,
      surnames: [{ name: "Коваленко", count: 14, variants: ["Kovalenko"] }],
      first_names: [{ name: "Іван", count: 2, variants: [] }],
      by_decade: [{ decade: 1860, births: 2, deaths: 0 }],
    };
    api({ "GET /api/v1/trees/t1/stats": () => json(stats) });
    renderWithProviders(<App />, { route: "/trees/t1/stats" });
    expect(await screen.findByText("1862–1998")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Степан Коваленко" })).toBeInTheDocument();
    expect(screen.getByText(/74 роки/)).toBeInTheDocument();
    expect(screen.getByText(/68.5 р\. \(за 11 людьми/)).toBeInTheDocument();
    expect(screen.getByText("(Kovalenko)")).toBeInTheDocument();
    expect(
      screen.getByRole("img", { name: "Народження і смерті за десятиліттями" }),
    ).toBeInTheDocument();
  });
});

describe("map", () => {
  it("lists places, shows a place's facts and the places without coordinates", async () => {
    api({
      "GET /api/v1/trees/t1/map": () =>
        json({
          points: [
            {
              latitude: "49.588300",
              longitude: "34.551400",
              label: "Полтава",
              place_id: "pl1",
              facts: [fact("e1", "birth", 1923), fact("e2", "residence", 1950)],
            },
            {
              latitude: "49.831000",
              longitude: "24.056000",
              label: "Личаківський цвинтар",
              place_id: "pl2",
              facts: [fact("e3", "burial", 1990)],
            },
          ],
          unplaced: 1,
          places_without_coordinates: [
            {
              id: "pl3",
              name: "Хутір",
              country: null,
              region: null,
              latitude: null,
              longitude: null,
            },
          ],
        }),
    });
    renderWithProviders(<App />, { route: "/trees/t1/map" });
    expect(await screen.findByRole("heading", { name: "2 місця" })).toBeInTheDocument();
    expect(screen.getByText(/1 подію не видно/)).toBeInTheDocument();
    expect(screen.getByText("Хутір")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /Полтава/ }));
    expect(screen.getByRole("heading", { name: "Полтава" })).toBeInTheDocument();
    expect(screen.getByText("Проживання")).toBeInTheDocument();

    // Category filter hides places without matching facts.
    await userEvent.click(screen.getByRole("button", { name: "Усі місця" }));
    await userEvent.click(screen.getByRole("button", { name: "Смерть і поховання" }));
    expect(await screen.findByRole("heading", { name: "1 місце" })).toBeInTheDocument();
  });
});
