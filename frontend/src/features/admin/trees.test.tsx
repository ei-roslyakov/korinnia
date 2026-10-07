import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "@/App";
import i18n from "@/i18n";
import { json, ME, mockApi } from "@/test/mockApi";
import { renderWithProviders } from "@/test/render";

vi.mock("@/features/tree/canvas/TreeCanvas", () => ({ TreeCanvas: () => <div /> }));

beforeEach(async () => {
  await i18n.changeLanguage("uk");
  document.cookie = "korinnia_csrf=x; path=/";
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

const row = (id: string, name: string, deleted_at: string | null = null) => ({
  id,
  name,
  is_demo: false,
  owner_id: "u2",
  owner_name: "Олена",
  owner_email: "olena@example.com",
  member_count: 3,
  person_count: 25,
  created_at: "2026-01-02T10:00:00Z",
  deleted_at,
});

describe("admin trees", () => {
  it("lists every tree, deletes one and restores a deleted one", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const calls: string[] = [];
    let live = [row("t1", "Коваленки"), row("t2", "Ткачуки")];
    mockApi({
      "GET /api/v1/auth/me": () => json({ ...ME, is_superadmin: true }),
      "GET /api/v1/admin/trees": ({ url }) => {
        calls.push(url);
        const deleted = url.includes("deleted=true");
        const items = deleted ? [row("t9", "Старий", "2026-05-01T10:00:00Z")] : live;
        return json({ items, total: items.length, limit: 50, offset: 0 });
      },
      "DELETE /api/v1/trees/t1": () => {
        live = live.filter((t) => t.id !== "t1");
        return json(null, 204);
      },
      "POST /api/v1/admin/trees/t9/restore": () => json(null, 204),
    });
    renderWithProviders(<App />, { route: "/admin/trees" });

    const kovalenky = (await screen.findByRole("link", { name: "Коваленки" })).closest("tr")!;
    expect(within(kovalenky).getByText("olena@example.com")).toBeInTheDocument();
    expect(within(kovalenky).getByText("25 людей · 3 учасники")).toBeInTheDocument();
    await userEvent.click(within(kovalenky).getByRole("button", { name: "Видалити" }));
    expect(window.confirm).toHaveBeenCalled();
    expect(await screen.findByRole("link", { name: "Ткачуки" })).toBeInTheDocument();
    await vi.waitFor(() =>
      expect(screen.queryByRole("link", { name: "Коваленки" })).not.toBeInTheDocument(),
    );

    await userEvent.selectOptions(screen.getByRole("combobox", { name: "Стан" }), "Видалені");
    const old = (await screen.findByText("Старий")).closest("tr")!;
    expect(calls.at(-1)).toContain("deleted=true");
    await userEvent.click(within(old).getByRole("button", { name: "Відновити" }));
    expect(calls.filter((c) => c.includes("deleted=true")).length).toBeGreaterThan(1);
  });

  it("lets a tree admin (not a superadmin) delete the tree from its settings", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    let deleted = false;
    mockApi({
      "GET /api/v1/auth/me": () => json(ME),
      "GET /api/v1/trees": () => json([]),
      "GET /api/v1/trees/t1": () =>
        json({ id: "t1", name: "Родина", description: null, my_role: "admin" }),
      "GET /api/v1/trees/t1/members": () => json({ members: [], invitations: [] }),
      "DELETE /api/v1/trees/t1": () => {
        deleted = true;
        return json(null, 204);
      },
    });
    renderWithProviders(<App />, { route: "/trees/t1/members" });
    await userEvent.click(await screen.findByRole("button", { name: "Видалити родовід" }));
    await vi.waitFor(() => expect(deleted).toBe(true));
  });
});
