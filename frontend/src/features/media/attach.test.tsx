import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "@/App";
import i18n from "@/i18n";
import { mediaItem } from "@/test/fixtures";
import { json, ME, mockApi } from "@/test/mockApi";
import { renderWithProviders } from "@/test/render";

vi.mock("@/features/builder/MapPicker", () => ({ MapPicker: () => <div /> }));

beforeEach(async () => {
  await i18n.changeLanguage("uk");
  document.cookie = "korinnia_csrf=x; path=/";
});
afterEach(() => vi.unstubAllGlobals());

describe("attaching media to a story", () => {
  it("picks files from the tree library and sends their ids", async () => {
    const sent: Record<string, unknown>[] = [];
    const scan = mediaItem("m7", "document_scan", { title: "Лист з фронту" });
    mockApi({
      "GET /api/v1/auth/me": () => json(ME),
      "GET /api/v1/trees/t1": () =>
        json({ id: "t1", name: "Родина", description: null, my_role: "contributor" }),
      "GET /api/v1/trees/t1/media": () =>
        json({ items: [scan, mediaItem("m8", "photo")], total: 2, limit: 60, offset: 0 }),
      "POST /api/v1/trees/t1/stories": (init) => {
        sent.push(JSON.parse(String(init.body)) as Record<string, unknown>);
        return json({ id: "st9", status: "draft" }, 201);
      },
    });
    renderWithProviders(<App />, { route: "/trees/t1/stories/new" });
    await userEvent.type(await screen.findByLabelText("Назва"), "Листи");
    await userEvent.click(screen.getByRole("button", { name: "+ Додати медіа" }));

    const dialog = within(await screen.findByRole("dialog", { name: "Медіатека родоводу" }));
    // Contributors choose from the library but cannot upload.
    expect(dialog.queryByText("Завантажити нові")).not.toBeInTheDocument();
    await userEvent.click(await dialog.findByRole("button", { name: "Лист з фронту" }));
    expect(dialog.getByText("Вибрано 1 файл")).toBeInTheDocument();
    await userEvent.click(dialog.getByRole("button", { name: "Готово" }));

    expect(screen.getByRole("button", { name: "Прибрати: Лист з фронту" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Зберегти чернетку" }));
    expect(sent[0]).toMatchObject({ title: "Листи", media_ids: ["m7"] });
  });
});
