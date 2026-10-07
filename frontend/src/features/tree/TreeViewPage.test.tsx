import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "@/App";
import i18n from "@/i18n";
import type { TreeGraph } from "@/lib/genealogy";
import { bigGraph, halyna, smallGraph } from "@/test/fixtures";
import { json, ME, mockApi } from "@/test/mockApi";
import { renderWithProviders } from "@/test/render";

import type { CenterRequest } from "./canvas/TreeCanvas";

// The real canvas (React Flow + ELK) is covered by unit tests and Playwright; here we
// check the page logic around it.
vi.mock("./canvas/TreeCanvas", () => ({
  TreeCanvas: (props: {
    included: Set<string>;
    focusMode: boolean;
    center: CenterRequest | null;
    onSelectPerson: (id: string) => void;
  }) => (
    <div data-testid="canvas">
      <span data-testid="mode">{props.focusMode ? "focus" : "all"}</span>
      <span data-testid="count">{props.included.size}</span>
      <span data-testid="center">{props.center?.personId ?? ""}</span>
      <button type="button" onClick={() => props.onSelectPerson("p2")}>
        card p2
      </button>
    </div>
  ),
}));

beforeEach(async () => {
  await i18n.changeLanguage("uk");
  document.cookie = "korinnia_csrf=x; path=/";
});
afterEach(() => vi.unstubAllGlobals());

function api(graph: TreeGraph, role = "viewer") {
  return mockApi({
    "GET /api/v1/auth/me": () => json(ME),
    "GET /api/v1/trees/t1": () =>
      json({ id: "t1", name: "Родина", description: null, my_role: role }),
    "GET /api/v1/trees/t1/graph": () => json(graph),
    "GET /api/v1/trees/t1/persons/p2": () => json(halyna),
    "GET /api/v1/trees/t1/persons": () =>
      json({ items: [graph.persons[1]], total: 1, limit: 12, offset: 0 }),
  });
}

describe("TreeViewPage", () => {
  it("shows the whole small tree and opens a person panel", async () => {
    api(smallGraph);
    renderWithProviders(<App />, { route: "/trees/t1" });
    expect(await screen.findByTestId("mode")).toHaveTextContent("all");
    expect(screen.getByTestId("count")).toHaveTextContent("2");
    expect(screen.getByText("Людей: 2")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "card p2" }));
    const panel = await screen.findByRole("complementary", { name: halyna.display_name });
    const p = within(panel);
    expect(p.getByRole("heading", { name: "Війна" })).toBeInTheDocument(); // Markdown biography
    expect(p.getByText("Львова")).toBeInTheDocument();
    expect(p.getByText(/Байкове кладовище, Ділянка 7/)).toBeInTheDocument();
    expect(p.getByRole("link", { name: "Показати на мапі" })).toHaveAttribute(
      "href",
      expect.stringContaining("openstreetmap.org"),
    );
    expect(p.getByText("Переїзд до Львова", { exact: false })).toBeInTheDocument();
    expect(p.getByRole("link", { name: "Ольга Ткачук" })).toHaveAttribute(
      "href",
      expect.stringContaining("person=p4"),
    );
    expect(p.getByText(/дівоче|Halyna Kovalenko/)).toBeInTheDocument();
    expect(p.getByText("Зберігайте листи.")).toBeInTheDocument();
    expect(p.queryByText("Примітки до даних")).not.toBeInTheDocument(); // viewers: no data notes

    await userEvent.click(p.getByRole("button", { name: "Зосередитися тут" }));
    expect(screen.getByTestId("mode")).toHaveTextContent("focus");
    expect(screen.getByTestId("center")).toHaveTextContent("p2");

    await userEvent.click(p.getByRole("button", { name: "Закрити" }));
    expect(screen.queryByRole("complementary")).not.toBeInTheDocument();
  });

  it("shows data notes to editors", async () => {
    api(smallGraph, "editor");
    renderWithProviders(<App />, { route: "/trees/t1?person=p2" });
    expect(await screen.findByText("Примітки до даних")).toBeInTheDocument();
    expect(screen.getByText(/лише 9/)).toBeInTheDocument();
  });

  it("opens large trees in focus mode and can show everything", async () => {
    api(bigGraph(200));
    renderWithProviders(<App />, { route: "/trees/t1" });
    expect(await screen.findByTestId("mode")).toHaveTextContent("focus");
    expect(Number(screen.getByTestId("count").textContent)).toBeLessThan(200);
    await userEvent.selectOptions(screen.getByLabelText("Покоління"), "1");
    expect(Number(screen.getByTestId("count").textContent)).toBe(3);
    await userEvent.click(screen.getByRole("button", { name: "Усе дерево" }));
    expect(screen.getByTestId("count")).toHaveTextContent("200");
  });

  it("search selects and centers a person", async () => {
    const fetch = api(smallGraph);
    renderWithProviders(<App />, { route: "/trees/t1" });
    const box = await screen.findByRole("combobox", { name: /Знайти людину/ });
    await userEvent.type(box, "halyna");
    const option = await screen.findByRole("option", { name: /Галина Коваленко/ });
    expect(option).toHaveTextContent("1923 – 2010");
    await userEvent.keyboard("{Enter}");
    await waitFor(() => expect(screen.getByTestId("center")).toHaveTextContent("p2"));
    expect(await screen.findByRole("complementary")).toBeInTheDocument();
    expect(fetch.mock.calls.some((c) => String(c[0]).includes("/persons?q=halyna"))).toBe(true);
  });

  it("explains an empty tree", async () => {
    api({ persons: [], parent_child: [], partnerships: [] });
    renderWithProviders(<App />, { route: "/trees/t1" });
    expect(await screen.findByText("У цьому родоводі ще немає людей.")).toBeInTheDocument();
    expect(screen.queryByRole("combobox", { name: /Знайти людину/ })).not.toBeInTheDocument();
  });
});

describe("PersonPage", () => {
  it("renders a person on its own page", async () => {
    api(smallGraph);
    renderWithProviders(<App />, { route: "/trees/t1/people/p2" });
    expect(await screen.findByRole("heading", { name: halyna.display_name })).toBeInTheDocument();
    expect(screen.getByText(/14 лютого 1923/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /До дерева/ })).toHaveAttribute(
      "href",
      "/trees/t1?person=p2",
    );
    // Linked twice: as parent and as event participant.
    for (const link of screen.getAllByRole("link", { name: "Йосип Шевчук" })) {
      expect(link).toHaveAttribute("href", "/trees/t1/people/p1");
    }
  });
});
