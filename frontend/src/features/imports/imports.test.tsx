import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "@/App";
import i18n from "@/i18n";
import { json, ME, mockApi } from "@/test/mockApi";
import { renderWithProviders } from "@/test/render";

import type { GedcomImport } from "./api";

beforeEach(async () => {
  await i18n.changeLanguage("uk");
  document.cookie = "korinnia_csrf=x; path=/";
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

const base: GedcomImport = {
  id: "i1",
  status: "analyzing",
  filename: "family.ged",
  size: 2048,
  created_at: "2026-10-08T10:00:00Z",
  finished_at: null,
  created_by: "Олена",
  preview: null,
  result: null,
  error: null,
};

const preview: GedcomImport["preview"] = {
  header: { source: "MyHeritage 5.5.1", version: "5.5.1", date: null },
  encoding: "UTF-8",
  counts: {
    persons: 4,
    families: 1,
    partnerships: 1,
    parent_links: 4,
    events: 9,
    places: 2,
    sources: 1,
    citations: 2,
    notes: 2,
    media_links: 1,
  },
  warnings: [{ code: "media_not_imported", count: 1 }],
  skipped_tags: [{ tag: "_CUSTOM", count: 1 }],
  people: [
    { xref: "@I1@", name: "Іван Коваленко", gender: "male", years: "1890 – 1944" },
    { xref: "@I2@", name: "Ганна Мельник", gender: "female", years: "1894 – 1971" },
  ],
  duplicates: [
    {
      xref: "@I1@",
      name: "Іван Коваленко",
      years: "1890 – 1944",
      strong: true,
      existing: { id: "p1", name: "Ivan Kovalenko", years: "1890" },
    },
    {
      xref: "@I2@",
      name: "Ганна Мельник",
      years: "1894 – 1971",
      strong: false,
      existing: { id: "p2", name: "Ганна Мельник", years: "" },
    },
  ],
};

describe("GEDCOM import page", () => {
  it("uploads, previews, imports with the chosen merges and undoes", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    let imp: GedcomImport = { ...base };
    let polls = 0;
    let uploaded: FormData | null = null;
    let confirmed: unknown = null;
    mockApi({
      "GET /api/v1/auth/me": () => json(ME),
      "GET /api/v1/trees/t1/imports": () => json(imp.status === "analyzing" ? [] : [imp]),
      "POST /api/v1/trees/t1/imports": ({ body }) => {
        uploaded = body as FormData;
        return json(imp, 202);
      },
      "GET /api/v1/trees/t1/imports/i1": () => {
        // The worker finishes the analysis after a poll.
        if (imp.status === "analyzing" && ++polls > 1) imp = { ...imp, status: "ready", preview };
        if (imp.status === "importing")
          imp = {
            ...imp,
            status: "done",
            result: {
              counts: { persons_created: 3, persons_merged: 1, partnerships: 1, warnings: 1 },
              warnings: [
                {
                  code: "link_skipped",
                  parent: "Богдан",
                  child: "Кирило",
                  reason: "too_many_biological_parents",
                },
              ],
            },
          };
        return json(imp);
      },
      "POST /api/v1/trees/t1/imports/i1/confirm": ({ body }) => {
        confirmed = JSON.parse(String(body));
        imp = { ...imp, status: "importing" };
        return json(imp);
      },
      "POST /api/v1/trees/t1/imports/i1/undo": () => {
        imp = { ...imp, status: "undone" };
        return json(imp);
      },
    });
    renderWithProviders(<App />, { route: "/trees/t1/import" });

    const file = new File(["0 HEAD\n0 TRLR\n"], "family.ged", { type: "text/plain" });
    await userEvent.upload(await screen.findByLabelText("Вибрати файл .ged"), file);
    await waitFor(() => expect(uploaded?.get("file")).toBeInstanceOf(File));

    // Preview: counts, warnings and the duplicates (strong match pre-ticked).
    expect(await screen.findByText("Уже є в цьому родоводі?", {}, { timeout: 4000 })).toBeVisible();
    expect(screen.getByText(/посилання на фото чи документ не імпортується/)).toBeVisible();
    expect(screen.getByText("_CUSTOM ×1")).toBeVisible();
    const same = screen.getAllByRole("checkbox", { name: "Та сама людина" });
    expect(same.map((c) => (c as HTMLInputElement).checked)).toEqual([true, false]);
    await userEvent.click(same[1]!);
    await userEvent.click(same[1]!);
    expect(screen.getByRole("button", { name: "Імпортувати (3 нові людини)" })).toBeEnabled();
    await userEvent.click(screen.getByRole("button", { name: "Імпортувати (3 нові людини)" }));
    expect(confirmed).toEqual({ merge: { "@I1@": "p1" } });

    expect(await screen.findByText("Родовід імпортовано.", {}, { timeout: 4000 })).toBeVisible();
    expect(screen.getByText("Створено 3 людини")).toBeVisible();
    await userEvent.click(screen.getByText("Пропущено 1 запис"));
    expect(screen.getByText(/Богдан → Кирило: зв'язок батьків і дитини не додано/)).toBeVisible();

    await userEvent.click(screen.getByRole("button", { name: "Скасувати імпорт" }));
    expect(window.confirm).toHaveBeenCalled();
    expect(await screen.findByText(/Цей імпорт скасовано/)).toBeVisible();
  });

  it("explains a file that is not GEDCOM", async () => {
    mockApi({
      "GET /api/v1/auth/me": () => json(ME),
      "GET /api/v1/trees/t1/imports": () => json([]),
      "POST /api/v1/trees/t1/imports": () => json({ code: "not_gedcom" }, 422),
    });
    renderWithProviders(<App />, { route: "/trees/t1/import" });
    const file = new File(["<html>"], "page.ged");
    await userEvent.upload(await screen.findByLabelText("Вибрати файл .ged"), file);
    expect(await screen.findByRole("alert")).toHaveTextContent("Це не файл GEDCOM.");
  });
});

describe("integrity card", () => {
  it("shows the last check, its problems and starts a new one", async () => {
    let started = false;
    mockApi({
      "GET /api/v1/auth/me": () => json({ ...ME, is_superadmin: true, can_create_trees: true }),
      "GET /api/v1/meta": () => json({ name: "Korinnia", version: "dev", environment: "dev" }),
      "GET /api/readyz": () => json({ status: "ok", checks: { database: "ok", storage: "ok" } }),
      "GET /api/v1/admin/integrity": () =>
        json({
          total_files: 120,
          total_bytes: 3 * 1024 ** 3,
          runs: [
            {
              id: "r1",
              status: "done",
              trigger: "scheduled",
              triggered_by: null,
              started_at: "2026-10-04T04:23:00Z",
              finished_at: "2026-10-04T04:40:00Z",
              files_checked: 120,
              bytes_checked: 3 * 1024 ** 3,
              problems: 1,
              untracked_files: 2,
              error: null,
            },
          ],
          issues: [
            {
              key: "originals/t1/m1/photo.jpg",
              problem: "hash_mismatch",
              media_id: "m1",
              tree_id: "t1",
              tree_name: "Родина",
              filename: "Весілля 1946",
              expected_size: 10,
              actual_size: 10,
            },
          ],
        }),
      "POST /api/v1/admin/integrity/run": () => {
        started = true;
        return json({ id: "r2", status: "running" }, 202);
      },
    });
    renderWithProviders(<App />, { route: "/admin/system" });
    const card = (await screen.findByRole("heading", { name: "Цілісність файлів" })).closest(
      "section",
    )!;
    const c = within(card as HTMLElement);
    expect(await c.findByText("Збережено 120 оригіналів (3 ГБ)")).toBeVisible();
    expect(c.getByText("1 проблема")).toBeVisible();
    expect(c.getByText(/2 файли у сховищі не пов'язані/)).toBeVisible();
    expect(c.getByText("Весілля 1946")).toBeVisible();
    expect(c.getByText("Змінився вміст")).toBeVisible();
    await userEvent.click(c.getByRole("button", { name: "Перевірити зараз" }));
    await waitFor(() => expect(started).toBe(true));
  });
});

describe("import into a new tree", () => {
  it("creates a tree named after the file and opens its import", async () => {
    let created: unknown = null;
    mockApi({
      "GET /api/v1/auth/me": () => json({ ...ME, is_superadmin: true, can_create_trees: true }),
      "GET /api/v1/trees": () => json([]),
      "POST /api/v1/trees": ({ body }) => {
        created = JSON.parse(String(body));
        return json({ id: "t9", name: "Kovalenko family", description: null, my_role: "admin" });
      },
      "POST /api/v1/trees/t9/imports": () => json({ ...base, id: "i9" }, 202),
      "GET /api/v1/trees/t9/imports": () => json([]),
      "GET /api/v1/trees/t9/imports/i9": () => json({ ...base, id: "i9" }),
    });
    renderWithProviders(<App />, { route: "/" });
    const file = new File(["0 HEAD\n"], "kovalenko_family.ged");
    // Both "Import GEDCOM" buttons (header and empty state) share one label; use the first.
    await userEvent.upload((await screen.findAllByLabelText("Імпорт GEDCOM"))[0]!, file);
    expect(await screen.findByRole("heading", { name: "Імпорт файлу GEDCOM" })).toBeVisible();
    expect(created).toEqual({ name: "Kovalenko family" });
    expect(await screen.findByText(/Для цього файлу створено новий родовід/)).toBeVisible();
  });

  it("removes the new tree when the file is refused", async () => {
    let deleted = false;
    mockApi({
      "GET /api/v1/auth/me": () => json({ ...ME, is_superadmin: true, can_create_trees: true }),
      "GET /api/v1/trees": () => json([]),
      "POST /api/v1/trees": () =>
        json({ id: "t9", name: "Page", description: null, my_role: "admin" }),
      "POST /api/v1/trees/t9/imports": () => json({ code: "not_gedcom" }, 422),
      "DELETE /api/v1/trees/t9": () => {
        deleted = true;
        return json(null, 204);
      },
    });
    renderWithProviders(<App />, { route: "/" });
    await userEvent.upload(
      (await screen.findAllByLabelText("Імпорт GEDCOM"))[0]!,
      new File(["<html>"], "page.ged"),
    );
    expect(await screen.findByText("Це не файл GEDCOM.")).toBeVisible();
    await waitFor(() => expect(deleted).toBe(true));
  });
});

describe("tree name from a file", () => {
  it("is readable", async () => {
    const { treeNameFromFile } = await import("./treeName");
    expect(treeNameFromFile("kovalenko_family-2024.ged")).toBe("Kovalenko family 2024");
    expect(treeNameFromFile("родина.GED")).toBe("Родина");
    expect(treeNameFromFile(".ged")).toBe("GEDCOM");
  });
});
