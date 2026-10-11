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

  it("lets a tree admin delete a tree from its card on the tree list", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const card = (id: string, name: string, my_role: string) => ({
      id,
      name,
      description: null,
      my_role,
      person_count: 0,
      cover: [],
    });
    let trees = [card("t1", "Моя родина", "admin"), card("t2", "Чужа родина", "viewer")];
    mockApi({
      "GET /api/v1/auth/me": () => json(ME),
      "GET /api/v1/trees": () => json(trees),
      "DELETE /api/v1/trees/t1": () => {
        trees = trees.filter((t) => t.id !== "t1");
        return json(null, 204);
      },
    });
    renderWithProviders(<App />, { route: "/" });
    expect(await screen.findByRole("link", { name: /Чужа родина/ })).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Видалити родовід «Чужа родина»" }),
    ).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Видалити родовід «Моя родина»" }));
    expect(window.confirm).toHaveBeenCalled();
    await vi.waitFor(() =>
      expect(screen.queryByRole("link", { name: /Моя родина/ })).not.toBeInTheDocument(),
    );
  });

  it("renames a tree from its card", async () => {
    let body: unknown = null;
    const tree = { id: "t1", description: null, my_role: "admin", person_count: 0 };
    let trees = [{ ...tree, name: "Стара назва" }];
    mockApi({
      "GET /api/v1/auth/me": () => json(ME),
      "GET /api/v1/trees": () => json(trees),
      "PATCH /api/v1/trees/t1": (init) => {
        body = JSON.parse(String(init.body));
        trees = [{ ...tree, name: "Нова назва" }];
        return json(trees[0]);
      },
    });
    renderWithProviders(<App />, { route: "/" });
    await userEvent.click(
      await screen.findByRole("button", { name: "Перейменувати родовід «Стара назва»" }),
    );
    const input = screen.getByRole("textbox", { name: "Назва" });
    await userEvent.clear(input);
    await userEvent.type(input, "Нова назва");
    await userEvent.click(screen.getByRole("button", { name: "Зберегти" }));
    expect(await screen.findByRole("link", { name: /Нова назва/ })).toBeInTheDocument();
    expect(body).toEqual({ name: "Нова назва" });
  });

  it("renames and deletes the open tree from builder mode, for admins only", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    let role = "editor";
    let name = "Родина";
    let deleted = false;
    const graph = { persons: [], parent_child: [], partnerships: [] };
    mockApi({
      "GET /api/v1/auth/me": () => json(ME),
      "GET /api/v1/trees": () => json([]),
      "GET /api/v1/trees/t1": () => json({ id: "t1", name, description: null, my_role: role }),
      "GET /api/v1/trees/t1/graph": () => json(graph),
      "PATCH /api/v1/trees/t1": (init) => {
        name = (JSON.parse(String(init.body)) as { name: string }).name;
        return json({ id: "t1", name, description: null, my_role: role });
      },
      "DELETE /api/v1/trees/t1": () => {
        deleted = true;
        return json(null, 204);
      },
    });
    const editor = renderWithProviders(<App />, { route: "/trees/t1?mode=edit" });
    expect(await screen.findByRole("heading", { name: "Родина" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Перейменувати родовід/ })).not.toBeInTheDocument();
    editor.unmount();

    role = "admin";
    renderWithProviders(<App />, { route: "/trees/t1?mode=edit" });
    await userEvent.click(
      await screen.findByRole("button", { name: "Перейменувати родовід «Родина»" }),
    );
    const input = screen.getByRole("textbox", { name: "Назва" });
    await userEvent.clear(input);
    await userEvent.type(input, "Наша родина");
    await userEvent.click(screen.getByRole("button", { name: "Зберегти" }));
    expect(await screen.findByRole("heading", { name: "Наша родина" })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Видалити родовід «Наша родина»" }));
    await vi.waitFor(() => expect(deleted).toBe(true));
    expect(await screen.findByRole("heading", { name: "Родоводи" })).toBeInTheDocument();
  });
});

describe("sharing a tree", () => {
  it("shares with an existing user and explains an unknown email", async () => {
    const sent: unknown[] = [];
    let members = [
      {
        user_id: "u1",
        email: "me@example.com",
        display_name: "Я",
        role: "admin",
        is_active: true,
        created_at: "2026-10-01T00:00:00Z",
      },
    ];
    mockApi({
      "GET /api/v1/auth/me": () => json(ME),
      "GET /api/v1/trees": () =>
        json([{ id: "t1", name: "Родина", description: null, my_role: "admin", person_count: 3 }]),
      "GET /api/v1/trees/t1/members": () => json({ members, invitations: [] }),
      "POST /api/v1/trees/t1/members": (init) => {
        const body = JSON.parse(String(init.body)) as { email: string; role: string };
        sent.push(body);
        if (body.email !== "olena@example.com") return json({ code: "no_user_with_email" }, 404);
        const member = {
          ...members[0]!,
          user_id: "u2",
          email: body.email,
          display_name: "Олена",
          role: body.role,
        };
        members = [...members, member];
        return json({ kind: "member", member, invitation: null, url: null }, 201);
      },
    });
    renderWithProviders(<App />, { route: "/" });
    await userEvent.click(
      await screen.findByRole("button", { name: "Поділитися родоводом «Родина»" }),
    );
    const dialog = within(await screen.findByRole("dialog"));
    expect(await dialog.findByText("me@example.com")).toBeInTheDocument();

    await userEvent.type(
      dialog.getByRole("textbox", { name: "Електронна пошта" }),
      "nobody@example.com",
    );
    await userEvent.click(dialog.getByRole("button", { name: "Поділитися" }));
    expect(await dialog.findByRole("alert")).toHaveTextContent(
      "Користувача з такою адресою не існує.",
    );

    const email = dialog.getByRole("textbox", { name: "Електронна пошта" });
    await userEvent.clear(email);
    await userEvent.type(email, "olena@example.com");
    await userEvent.selectOptions(dialog.getByRole("combobox", { name: "Доступ" }), "editor");
    await userEvent.click(dialog.getByRole("button", { name: "Поділитися" }));
    expect(await dialog.findByText("Тепер родовід доступний для Олена.")).toBeInTheDocument();
    expect(await dialog.findByText("olena@example.com")).toBeInTheDocument();
    expect(sent).toEqual([
      { email: "nobody@example.com", role: "viewer", invite: false },
      { email: "olena@example.com", role: "editor", invite: false },
    ]);
  });
});
