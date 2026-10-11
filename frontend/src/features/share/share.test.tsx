import { screen, waitFor, within } from "@testing-library/react";
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
afterEach(() => vi.unstubAllGlobals());

const loggedOut = {
  "GET /api/v1/auth/me": () => json({ code: "not_authenticated" }, 401),
  "POST /api/v1/auth/refresh": () => json({ code: "not_authenticated" }, 401),
};

describe("opening a share link", () => {
  it("lets a visitor without an account view the tree", async () => {
    let opened = false;
    mockApi({
      ...loggedOut,
      "POST /api/v1/share/tok123/open": () => {
        opened = true;
        return json({ tree_id: "t1", tree_name: "Родина", expires_at: null });
      },
      "GET /api/v1/share/session": () =>
        opened
          ? json({ tree_id: "t1", tree_name: "Родина", expires_at: null })
          : json({ code: "no_share_session" }, 401),
      "GET /api/v1/trees/t1": () =>
        json({ id: "t1", name: "Родина", description: null, my_role: "viewer" }),
      "GET /api/v1/trees/t1/graph": () => json({ persons: [], parent_child: [], partnerships: [] }),
    });
    renderWithProviders(<App />, { route: "/s/tok123" });
    expect(await screen.findByRole("heading", { name: "Родина" })).toBeInTheDocument();
    expect(screen.getByText("Перегляд за посиланням")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Увійти" })).toHaveAttribute("href", "/login");
    // Read-only: no builder switch.
    expect(screen.queryByRole("button", { name: "Редагування" })).not.toBeInTheDocument();
  });

  it("explains a link that no longer works", async () => {
    mockApi({
      ...loggedOut,
      "POST /api/v1/share/old/open": () => json({ code: "share_link_invalid" }, 404),
    });
    renderWithProviders(<App />, { route: "/s/old" });
    expect(await screen.findByText("Це посилання більше не діє")).toBeInTheDocument();
  });

  it("still sends visitors without a link to the sign-in page", async () => {
    mockApi({
      ...loggedOut,
      "GET /api/v1/share/session": () => json({ code: "no_share_session" }, 401),
      "GET /api/v1/meta": () => json({ name: "Korinnia", version: "dev", environment: "dev" }),
    });
    renderWithProviders(<App />, { route: "/trees/t1" });
    expect(await screen.findByRole("button", { name: "Увійти" })).toBeInTheDocument();
  });
});

describe("managing share links", () => {
  it("creates a link, shows it once and revokes it", async () => {
    let links: unknown[] = [];
    let body: unknown = null;
    mockApi({
      "GET /api/v1/auth/me": () => json(ME),
      "GET /api/v1/trees": () =>
        json([{ id: "t1", name: "Родина", description: null, my_role: "admin", person_count: 3 }]),
      "GET /api/v1/trees/t1/members": () => json({ members: [], invitations: [] }),
      "GET /api/v1/trees/t1/share-links": () => json(links),
      "POST /api/v1/trees/t1/share-links": (init) => {
        body = JSON.parse(String(init.body));
        const link = {
          id: "l1",
          label: "Для зустрічі",
          created_at: "2026-10-11T10:00:00Z",
          created_by: "Галина",
          expires_at: null,
          revoked_at: null,
          last_used_at: null,
          use_count: 2,
          active: true,
        };
        links = [link];
        return json({ link, url: "https://korinnia.app/s/abc" }, 201);
      },
      "DELETE /api/v1/trees/t1/share-links/l1": () => {
        links = [];
        return json(null, 204);
      },
    });
    renderWithProviders(<App />, { route: "/" });
    await userEvent.click(
      await screen.findByRole("button", { name: "Поділитися родоводом «Родина»" }),
    );
    const dialog = within(await screen.findByRole("dialog"));
    await userEvent.type(
      dialog.getByRole("textbox", { name: "Назва (необов'язково)" }),
      "Для зустрічі",
    );
    await userEvent.selectOptions(dialog.getByRole("combobox", { name: "Діє" }), "never");
    await userEvent.click(dialog.getByRole("button", { name: "Створити посилання" }));
    expect(await dialog.findByDisplayValue("https://korinnia.app/s/abc")).toBeInTheDocument();
    expect(body).toEqual({ label: "Для зустрічі", expires_in_days: null });
    expect(await dialog.findByText(/відкрито 2 рази/)).toBeInTheDocument();
    await userEvent.click(dialog.getByRole("button", { name: "Відкликати" }));
    await waitFor(() => expect(dialog.queryByText(/відкрито 2 рази/)).not.toBeInTheDocument());
  });
});
