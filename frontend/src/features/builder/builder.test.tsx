import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "@/App";
import i18n from "@/i18n";
import type { TreeGraph } from "@/lib/genealogy";
import { halyna, smallGraph, summary } from "@/test/fixtures";
import { json, ME, mockApi, type Handler } from "@/test/mockApi";
import { renderWithProviders } from "@/test/render";

vi.mock("@/features/tree/canvas/TreeCanvas", () => ({
  TreeCanvas: (props: { builder: boolean; onAddRelative?: (id: string, rel: string) => void }) => (
    <div data-testid="canvas">
      <span data-testid="builder">{props.builder ? "on" : "off"}</span>
      <button type="button" onClick={() => props.onAddRelative?.("p2", "child")}>
        plus child of p2
      </button>
    </div>
  ),
}));
vi.mock("./MapPicker", () => ({ MapPicker: () => <div data-testid="map" /> }));

beforeEach(async () => {
  await i18n.changeLanguage("uk");
  document.cookie = "korinnia_csrf=x; path=/";
  localStorage.clear();
});
afterEach(() => vi.unstubAllGlobals());

const body = (init: RequestInit) => JSON.parse(String(init.body)) as Record<string, unknown>;

function api(role: string, extra: Record<string, Handler> = {}, graph: TreeGraph = smallGraph) {
  return mockApi({
    "GET /api/v1/auth/me": () => json(ME),
    "GET /api/v1/trees/t1": () =>
      json({ id: "t1", name: "Родина", description: null, my_role: role }),
    "GET /api/v1/trees/t1/graph": () => json(graph),
    "GET /api/v1/trees/t1/persons/p2": () => json(halyna),
    "GET /api/v1/trees/t1/places": () => json({ items: [], total: 0, limit: 10, offset: 0 }),
    ...extra,
  });
}

describe("builder mode on the tree page", () => {
  it("is offered to editors only", async () => {
    api("viewer");
    const { unmount } = renderWithProviders(<App />, { route: "/trees/t1?mode=edit" });
    expect(await screen.findByTestId("builder")).toHaveTextContent("off");
    expect(screen.queryByRole("button", { name: "Редагування" })).not.toBeInTheDocument();
    unmount();

    api("editor");
    renderWithProviders(<App />, { route: "/trees/t1" });
    await userEvent.click(await screen.findByRole("button", { name: "Редагування" }));
    expect(screen.getByTestId("builder")).toHaveTextContent("on");
    expect(screen.getByRole("link", { name: "Кошик" })).toHaveAttribute("href", "/trees/t1/trash");
  });

  it("adds a child from a card's + button", async () => {
    let sent: Record<string, unknown> = {};
    api("editor", {
      "POST /api/v1/trees/t1/persons": (init) => {
        sent = body(init);
        return json({ ...halyna, id: "new1", display_name: "Петро Коваленко" }, 201);
      },
    });
    renderWithProviders(<App />, { route: "/trees/t1?mode=edit" });
    await userEvent.click(await screen.findByRole("button", { name: "plus child of p2" }));
    const dialog = await screen.findByRole("dialog");
    const d = within(dialog);
    await waitFor(() => expect(d.getByLabelText("Прізвище")).toHaveValue("Коваленко")); // suggested
    await userEvent.type(d.getByLabelText("Ім’я"), "Петро");
    await userEvent.selectOptions(d.getByLabelText("Інший з батьків"), "p3");
    await userEvent.selectOptions(d.getByLabelText("Народження: точність"), "approx");
    await userEvent.type(d.getByLabelText("Народження: Рік"), "1950");
    await userEvent.click(d.getByRole("button", { name: "Створити" }));
    await waitFor(() => expect(sent.relative).toBeTruthy());
    expect(sent).toMatchObject({
      names: [{ first_name: "Петро", last_name: "Коваленко", is_primary: true }],
      birth: { date: { precision: "approx", year: 1950 } },
      relative: { person_id: "p2", relation: "child", other_parent_id: "p3" },
    });
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("shows server validation errors in the dialog", async () => {
    api("editor", {
      "POST /api/v1/trees/t1/persons": () => json({ code: "too_many_biological_parents" }, 409),
    });
    renderWithProviders(<App />, { route: "/trees/t1?mode=edit" });
    await userEvent.click(await screen.findByRole("button", { name: "plus child of p2" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Створити" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent(
      "не більше двох рідних батьків",
    );
  });
});

describe("person editor", () => {
  it("edits details, biography with draft, and saves", async () => {
    let patch: Record<string, unknown> = {};
    api("editor", {
      "PATCH /api/v1/trees/t1/persons/p2": (init) => {
        patch = body(init);
        return json({
          ...halyna,
          warnings: [{ code: "lifespan_too_long", params: { years: 130 } }],
        });
      },
    });
    localStorage.setItem(
      "korinnia.draft.p2.biography",
      JSON.stringify({ text: "Чернетка з минулого разу", savedAt: "2026-01-01T10:00:00Z" }),
    );
    renderWithProviders(<App />, { route: "/trees/t1/people/p2/edit" });
    expect(await screen.findByRole("heading", { name: halyna.display_name })).toBeInTheDocument();

    // Unsaved draft is offered.
    await userEvent.click(screen.getByRole("button", { name: "Відновити чернетку" }));
    expect(screen.getByLabelText("Біографія")).toHaveValue("Чернетка з минулого разу");
    await userEvent.click(screen.getAllByRole("tab", { name: "Перегляд" })[0]!);
    expect(screen.getByText("Чернетка з минулого разу")).toBeInTheDocument();

    await userEvent.clear(screen.getByLabelText("Заняття"));
    await userEvent.type(screen.getByLabelText("Заняття"), "Директорка школи");
    expect(screen.getByText("Є незбережені зміни")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Зберегти" }));
    await waitFor(() => expect(patch.occupation).toBe("Директорка школи"));
    expect(patch).toMatchObject({
      biography: "Чернетка з минулого разу",
      birth: { date: { precision: "exact", year: 1923, month: 2, day: 14 }, place_id: "pl1" },
      death: { date: { precision: "year", year: 2010 }, place_id: null },
    });
    expect((patch.names as unknown[]).length).toBe(2);
    expect(await screen.findByText(/130 років/)).toBeInTheDocument(); // warning shown
    expect(localStorage.getItem("korinnia.draft.p2.biography")).toBeNull(); // draft cleared
  });

  it("adds an event with a participant", async () => {
    let sent: Record<string, unknown> = {};
    api("editor", {
      "POST /api/v1/trees/t1/events": (init) => {
        sent = body(init);
        return json({ id: "ev9" }, 201);
      },
      "GET /api/v1/trees/t1/persons": () =>
        json({ items: [summary("p5", "Михайло Ткачук")], total: 1, limit: 12, offset: 0 }),
    });
    renderWithProviders(<App />, { route: "/trees/t1/people/p2/edit?tab=events" });
    expect(await screen.findByText(/Переїзд до Львова/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "+ Додати подію" }));
    const d = within(await screen.findByRole("dialog"));
    await userEvent.selectOptions(d.getByLabelText("Тип"), "emigration");
    await userEvent.type(d.getByLabelText("Назва"), "Виїзд до Канади");
    await userEvent.selectOptions(d.getByLabelText("Дата: точність"), "year");
    await userEvent.type(d.getByLabelText("Дата: Рік"), "1949");
    await userEvent.type(d.getByRole("combobox", { name: "Додати учасника…" }), "Мих");
    await userEvent.click(await d.findByRole("option", { name: /Михайло Ткачук/ }));
    await userEvent.click(d.getByRole("button", { name: "Зберегти" }));
    await waitFor(() => expect(sent.type).toBe("emigration"));
    expect(sent).toMatchObject({
      title: "Виїзд до Канади",
      date: { precision: "year", year: 1949 },
      participants: [
        { person_id: "p2", role: "principal" },
        { person_id: "p5", role: "other" },
      ],
    });
  });

  it("changes relationship types and links existing people", async () => {
    const calls: { method: string; path: string; body: Record<string, unknown> }[] = [];
    const record = (method: string, path: string) => (init: RequestInit) => {
      calls.push({ method, path, body: init.body ? body(init) : {} });
      return json({}, method === "POST" ? 201 : 200);
    };
    api("editor", {
      "PATCH /api/v1/trees/t1/parent-child/e1": record("PATCH", "e1"),
      "POST /api/v1/trees/t1/parent-child": record("POST", "pc"),
      "GET /api/v1/trees/t1/persons": () =>
        json({ items: [summary("p9", "Новий Син")], total: 1, limit: 12, offset: 0 }),
    });
    renderWithProviders(<App />, { route: "/trees/t1/people/p2/edit?tab=family" });
    const selects = await screen.findAllByLabelText("Зв’язок");
    await userEvent.selectOptions(selects[0]!, "adoptive");
    await waitFor(() =>
      expect(calls[0]).toEqual({ method: "PATCH", path: "e1", body: { type: "adoptive" } }),
    );
    const pickers = screen.getAllByRole("combobox", { name: "Пов’язати з наявною людиною…" });
    await userEvent.type(pickers[2]!, "Нов"); // children section
    await userEvent.click(await screen.findByRole("option", { name: /Новий Син/ }));
    await waitFor(() =>
      expect(calls[1]).toEqual({
        method: "POST",
        path: "pc",
        body: { parent_id: "p2", child_id: "p9", type: "biological" },
      }),
    );
  });

  it("shows history and restores a version", async () => {
    let restored = "";
    api("editor", {
      "GET /api/v1/trees/t1/history": () =>
        json({
          items: [
            {
              id: "h2",
              created_at: "2026-02-01T10:00:00Z",
              user_id: null,
              user_label: "owner@example.com",
              action: "person.update",
              entity_type: "person",
              entity_id: "p2",
              tree_id: "t1",
              before: { occupation: "Вчителька", names: [] },
              after: { occupation: "Директорка", names: [] },
              ip_address: null,
            },
            {
              id: "h1",
              created_at: "2026-01-01T10:00:00Z",
              user_id: null,
              user_label: "owner@example.com",
              action: "person.create",
              entity_type: "person",
              entity_id: "p2",
              tree_id: "t1",
              before: null,
              after: { occupation: "Вчителька" },
              ip_address: null,
            },
          ],
          total: 2,
          limit: 100,
          offset: 0,
        }),
      "POST /api/v1/trees/t1/history/h1/restore": () => {
        restored = "h1";
        return json({ entity_type: "person", entity_id: "p2" });
      },
    });
    vi.spyOn(window, "confirm").mockReturnValue(true);
    renderWithProviders(<App />, { route: "/trees/t1/people/p2/edit?tab=history" });
    expect(await screen.findByText("Змінено: заняття")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Відновити цю версію" })).toHaveLength(1);
    await userEvent.click(screen.getByRole("button", { name: "Відновити цю версію" }));
    await waitFor(() => expect(restored).toBe("h1"));
  });

  it("previews and confirms deletion", async () => {
    let deleted = false;
    api("editor", {
      "GET /api/v1/trees/t1/persons/p2/delete-preview": () =>
        json({
          person: summary("p2", "Галина"),
          parent_links: 1,
          child_links: 2,
          partnerships: 1,
          events: 3,
          shared_events: 1,
        }),
      "DELETE /api/v1/trees/t1/persons/p2": () => {
        deleted = true;
        return json(null, 204);
      },
    });
    renderWithProviders(<App />, { route: "/trees/t1/people/p2/edit" });
    await userEvent.click(await screen.findByRole("button", { name: "Видалити" }));
    const d = within(await screen.findByRole("dialog"));
    expect(await d.findByText("Зв’язки з дітьми: 2")).toBeInTheDocument();
    expect(d.getByText(/Спільні події/)).toBeInTheDocument();
    await userEvent.click(d.getByRole("button", { name: "Перемістити до кошика" }));
    await waitFor(() => expect(deleted).toBe(true));
  });

  it("is refused to viewers", async () => {
    api("viewer");
    renderWithProviders(<App />, { route: "/trees/t1/people/p2/edit" });
    expect(await screen.findByRole("alert")).toHaveTextContent("У вас немає прав");
  });
});

describe("trash page", () => {
  it("lists and restores deleted items", async () => {
    let restored = "";
    api("editor", {
      "GET /api/v1/trees/t1/trash": () =>
        json([
          {
            entity_type: "person",
            entity_id: "p7",
            label: "Тато Коваленко",
            deleted_at: "2026-03-01T10:00:00Z",
            deleted_by: "owner@example.com",
            batch_size: 4,
          },
        ]),
      "POST /api/v1/trees/t1/trash/person/p7/restore": () => {
        restored = "p7";
        return json(null, 204);
      },
    });
    renderWithProviders(<App />, { route: "/trees/t1/trash" });
    expect(await screen.findByText("Тато Коваленко")).toBeInTheDocument();
    expect(screen.getByText(/пов’язаних записів: 4/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Відновити" }));
    await waitFor(() => expect(restored).toBe("p7"));
  });
});
