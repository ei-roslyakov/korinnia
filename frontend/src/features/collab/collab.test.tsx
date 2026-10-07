import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "@/App";
import i18n from "@/i18n";
import { halyna, smallGraph, summary } from "@/test/fixtures";
import { json, ME, mockApi, type Handler } from "@/test/mockApi";
import { renderWithProviders } from "@/test/render";

vi.mock("@/features/tree/canvas/TreeCanvas", () => ({ TreeCanvas: () => <div /> }));
vi.mock("@/features/builder/MapPicker", () => ({ MapPicker: () => <div /> }));

beforeEach(async () => {
  await i18n.changeLanguage("uk");
  document.cookie = "korinnia_csrf=x; path=/";
});
afterEach(() => vi.unstubAllGlobals());

const body = (init: RequestInit) => JSON.parse(String(init.body)) as Record<string, unknown>;
const comment = {
  id: "cm1",
  entity_type: "person",
  entity_id: "p2",
  body: "Пам'ятаю пироги",
  author: { id: "u1", display_name: "Галина" },
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
};

function api(role: string, extra: Record<string, Handler> = {}) {
  return mockApi({
    "GET /api/v1/auth/me": () => json(ME),
    "GET /api/v1/trees/t1": () =>
      json({ id: "t1", name: "Родина", description: null, my_role: role }),
    "GET /api/v1/trees/t1/graph": () => json(smallGraph),
    "GET /api/v1/trees/t1/persons/p2": () => json(halyna),
    "GET /api/v1/trees/t1/comments": () => json([comment]),
    "GET /api/v1/trees/t1/moderation": () => json({ suggestions: 2, stories: 1 }),
    ...extra,
  });
}

describe("person page collaboration", () => {
  it("shows sources, stories, questions and comments read-only to viewers", async () => {
    api("viewer");
    renderWithProviders(<App />, { route: "/trees/t1/people/p2" });
    expect(await screen.findByRole("heading", { name: "Джерела" })).toBeInTheDocument();
    expect(screen.getByText("Метрична книга, Станиславів")).toBeInTheDocument();
    expect(screen.getByText(/Народження · 1923-02-14/)).toBeInTheDocument();
    expect(screen.getByText("Первинне джерело")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Як ми їхали до Львова" })).toHaveAttribute(
      "href",
      "/trees/t1/stories/st1",
    );
    expect(screen.getByText("Де вона вчилася?")).toBeInTheDocument();
    expect(await screen.findByText("Пам'ятаю пироги")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Додати коментар" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Запропонувати зміну" })).not.toBeInTheDocument();
  });

  it("lets contributors comment, ask questions and suggest edits", async () => {
    const sent: Record<string, unknown>[] = [];
    api("contributor", {
      "POST /api/v1/trees/t1/comments": (init) => (sent.push(body(init)), json(comment, 201)),
      "POST /api/v1/trees/t1/questions": (init) => (sent.push(body(init)), json({}, 201)),
      "POST /api/v1/trees/t1/suggestions": (init) => (sent.push(body(init)), json({}, 201)),
    });
    renderWithProviders(<App />, { route: "/trees/t1/people/p2" });
    await userEvent.type(
      await screen.findByRole("textbox", { name: "Додати коментар" }),
      "Вона співала в хорі",
    );
    await userEvent.click(screen.getByRole("button", { name: "Додати коментар" }));
    await userEvent.type(screen.getByRole("textbox", { name: "Додати питання" }), "Де похована?");
    await userEvent.click(screen.getByRole("button", { name: "Додати питання" }));

    await userEvent.click(screen.getByRole("button", { name: "Запропонувати зміну" }));
    const d = within(await screen.findByRole("dialog"));
    expect(d.getByRole("button", { name: "Надіслати пропозицію" })).toBeDisabled();
    await userEvent.clear(d.getByLabelText("Заняття"));
    await userEvent.type(d.getByLabelText("Заняття"), "Директорка школи");
    await userEvent.type(d.getByLabelText(/Звідки ця інформація/), "Зі слів доньки");
    await userEvent.click(d.getByRole("button", { name: "Надіслати пропозицію" }));
    expect(await d.findByText(/Пропозицію надіслано/)).toBeInTheDocument();
    expect(sent).toEqual([
      { entity_type: "person", entity_id: "p2", body: "Вона співала в хорі" },
      { person_id: "p2", question: "Де похована?" },
      {
        entity_type: "person",
        entity_id: "p2",
        patch: { occupation: "Директорка школи" },
        comment: "Зі слів доньки",
      },
    ]);
  });
});

describe("moderation", () => {
  it("shows pending counts and approves a suggestion with before/after", async () => {
    let decision = "";
    api("editor", {
      "GET /api/v1/trees/t1/suggestions": () =>
        json([
          {
            id: "sg1",
            entity_type: "person",
            entity_id: "p2",
            entity_label: "Галина",
            patch: { occupation: "Директорка" },
            current: { occupation: "Вчителька" },
            comment: "Зі слів доньки",
            status: "pending",
            author: { id: "u2", display_name: "Оля" },
            reviewer: null,
            review_comment: null,
            reviewed_at: null,
            created_at: "2024-01-01T00:00:00Z",
          },
        ]),
      "GET /api/v1/trees/t1/stories": () => json({ items: [], total: 0, limit: 200, offset: 0 }),
      "POST /api/v1/trees/t1/suggestions/sg1/approve": () => ((decision = "approve"), json({})),
    });
    renderWithProviders(<App />, { route: "/trees/t1" });
    expect(await screen.findByLabelText("На перевірці: 3")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("link", { name: /Модерація/ }));
    expect(await screen.findByText("Вчителька")).toBeInTheDocument();
    expect(screen.getByText("Директорка")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Схвалити й застосувати" }));
    await waitFor(() => expect(decision).toBe("approve"));
  });
});

describe("stories", () => {
  it("contributor writes a story and submits it for review", async () => {
    const calls: string[] = [];
    let created: Record<string, unknown> = {};
    const story = {
      id: "st9",
      title: "Пироги",
      excerpt: "",
      narrator: null,
      date: null,
      status: "draft",
      author: ME,
      person_ids: ["p2"],
      updated_at: "x",
      body: "",
      persons: [],
      media: [],
      review_comment: null,
      can_edit: true,
      created_at: "x",
    };
    api("contributor", {
      "GET /api/v1/trees/t1/persons": () =>
        json({ items: [summary("p2", "Галина Коваленко")], total: 1, limit: 12, offset: 0 }),
      "POST /api/v1/trees/t1/stories": (init) => ((created = body(init)), json(story, 201)),
      "POST /api/v1/trees/t1/stories/st9/submit": () => (
        calls.push("submit"),
        json({ ...story, status: "pending_review" })
      ),
      "GET /api/v1/trees/t1/stories/st9": () => json({ ...story, status: "pending_review" }),
    });
    renderWithProviders(<App />, { route: "/trees/t1/stories/new" });
    await userEvent.type(await screen.findByLabelText("Назва"), "Пироги");
    await userEvent.type(screen.getByLabelText("Оповідач"), "бабуся Галина");
    await userEvent.type(screen.getByRole("combobox", { name: /Додати людину/ }), "Гал");
    await userEvent.click(await screen.findByRole("option", { name: /Галина Коваленко/ }));
    await userEvent.type(screen.getByLabelText("Історія"), "Тісто місили з вечора.");
    expect(screen.queryByRole("button", { name: "Опублікувати" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Надіслати на перевірку" }));
    await waitFor(() => expect(calls).toEqual(["submit"]));
    expect(created).toMatchObject({
      title: "Пироги",
      narrator: "бабуся Галина",
      person_ids: ["p2"],
      body: "Тісто місили з вечора.",
      status: "draft",
    });
    expect(await screen.findByText("На перевірці")).toBeInTheDocument();
  });
});

describe("citing sources in the editor", () => {
  it("creates a source inline and cites it for the burial", async () => {
    let citation: Record<string, unknown> = {};
    api("editor", {
      "GET /api/v1/trees/t1/sources": () => json({ items: [], total: 0, limit: 100, offset: 0 }),
      "POST /api/v1/trees/t1/sources": (init) =>
        json({ id: "s9", ...body(init), media: [], citation_count: 0 }, 201),
      "POST /api/v1/trees/t1/citations": (init) => ((citation = body(init)), json({}, 201)),
    });
    renderWithProviders(<App />, { route: "/trees/t1/people/p2/edit?tab=sources" });
    await userEvent.click(await screen.findByRole("button", { name: "+ Послатися на джерело" }));
    const d = within(await screen.findByRole("dialog"));
    await userEvent.selectOptions(
      d.getByLabelText("Що підтверджує"),
      d.getByRole("option", { name: /Поховання/ }),
    );
    await userEvent.type(d.getByLabelText("Пошук джерел…"), "Метрика");
    await userEvent.click(d.getByRole("button", { name: "+ Нове джерело" }));
    const sd = within(screen.getAllByRole("dialog").at(-1)!);
    expect(sd.getByLabelText("Назва")).toHaveValue("Метрика");
    await userEvent.click(sd.getByRole("button", { name: "Зберегти" }));
    await userEvent.type(d.getByLabelText("Сторінка / аркуш"), "арк. 34");
    await userEvent.click(d.getByRole("button", { name: "Зберегти" }));
    await waitFor(() =>
      expect(citation).toEqual({
        source_id: "s9",
        entity_type: "event",
        entity_id: "ev3",
        field: null,
        page: "арк. 34",
        quality: "primary",
        notes: null,
      }),
    );
  });
});

describe("data quality", () => {
  it("lists research to-dos with counts", async () => {
    api("contributor", {
      "GET /api/v1/trees/t1/data-quality": () =>
        json({
          counts: {
            people: 25,
            missing_birth: 1,
            missing_photo: 20,
            without_sources: 18,
            date_problems: 1,
            open_questions: 0,
          },
          missing_birth: [summary("p7", "Невідомий")],
          missing_photo: [],
          without_sources: [],
          date_problems: [
            {
              person: summary("p8", "Дитина"),
              warnings: [{ code: "child_born_before_parent", params: {} }],
            },
          ],
          open_questions: [],
        }),
    });
    renderWithProviders(<App />, { route: "/trees/t1/quality" });
    expect(await screen.findByRole("heading", { name: "Якість даних" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Невідомий" })).toHaveAttribute(
      "href",
      "/trees/t1/people/p7",
    );
    expect(screen.getByText("Дитина народилася раніше за одного з батьків.")).toBeInTheDocument();
    expect(screen.getAllByText("Тут усе гаразд 🎉").length).toBeGreaterThan(0);
  });
});
