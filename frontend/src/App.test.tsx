import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";
import i18n from "./i18n";
import { safeNext } from "./lib/nav";
import { json, ME, mockApi } from "./test/mockApi";
import { renderWithProviders } from "./test/render";

beforeEach(async () => {
  await i18n.changeLanguage("uk");
  document.cookie = "korinnia_csrf=csrf-123; path=/";
});
afterEach(() => vi.unstubAllGlobals());

const loggedOut = {
  "GET /api/v1/auth/me": () => json({ code: "not_authenticated" }, 401),
  "POST /api/v1/auth/refresh": () => json({ code: "not_authenticated" }, 401),
};

describe("App", () => {
  it("redirects anonymous users to the login page", async () => {
    mockApi(loggedOut);
    renderWithProviders(<App />, { route: "/trees/t1" });
    expect(await screen.findByRole("button", { name: "Увійти" })).toBeInTheDocument();
  });

  it("logs in and shows the user's trees", async () => {
    let loggedIn = false;
    mockApi({
      "GET /api/v1/auth/me": () => (loggedIn ? json(ME) : json({}, 401)),
      "POST /api/v1/auth/refresh": () => json({}, 401),
      "POST /api/v1/auth/login": () => {
        loggedIn = true;
        return json({ status: "ok", user: ME });
      },
      "GET /api/v1/trees": () =>
        json([{ id: "t1", name: "Родина", description: null, my_role: "viewer" }]),
    });
    renderWithProviders(<App />, { route: "/login" });
    await userEvent.type(await screen.findByLabelText("Електронна пошта"), "halyna@example.com");
    await userEvent.type(screen.getByLabelText("Пароль"), "correct-horse-battery");
    await userEvent.click(screen.getByRole("button", { name: "Увійти" }));
    expect(await screen.findByRole("heading", { name: "Родина" })).toBeInTheDocument();
    expect(screen.getByText("Глядач")).toBeInTheDocument();
    expect(screen.queryByText("Адміністрування")).not.toBeInTheDocument();
  });

  it("asks for a second factor when 2FA is enabled", async () => {
    const fetch = mockApi({
      ...loggedOut,
      "POST /api/v1/auth/login": () => json({ status: "mfa_required", user: null }),
      "POST /api/v1/auth/login/mfa": () => json({ code: "invalid_code" }, 401),
    });
    renderWithProviders(<App />, { route: "/login" });
    await userEvent.type(await screen.findByLabelText("Електронна пошта"), "a@b.cz");
    await userEvent.type(screen.getByLabelText("Пароль"), "x");
    await userEvent.click(screen.getByRole("button", { name: "Увійти" }));
    await userEvent.type(await screen.findByLabelText("Код"), "123456");
    await userEvent.click(screen.getByRole("button", { name: "Підтвердити" }));
    expect(await screen.findByText("Код недійсний.")).toBeInTheDocument();
    const mfaCall = fetch.mock.calls.find((c) => c[0] === "/api/v1/auth/login/mfa");
    expect((mfaCall?.[1] as RequestInit).body).toBe('{"code":"123456"}');
  });

  it("shows a translated error for wrong credentials", async () => {
    mockApi({
      ...loggedOut,
      "POST /api/v1/auth/login": () => json({ code: "invalid_credentials" }, 401),
    });
    renderWithProviders(<App />, { route: "/login" });
    await userEvent.type(await screen.findByLabelText("Електронна пошта"), "a@b.cz");
    await userEvent.type(screen.getByLabelText("Пароль"), "x");
    await userEvent.click(screen.getByRole("button", { name: "Увійти" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Неправильна пошта або пароль.");
  });

  it("shows admin navigation and member management to a superadmin", async () => {
    mockApi({
      "GET /api/v1/auth/me": () => json({ ...ME, is_superadmin: true, can_create_trees: true }),
      "GET /api/v1/trees/t1": () =>
        json({ id: "t1", name: "Родина", description: "Полтава", my_role: "admin" }),
      "GET /api/v1/trees/t1/graph": () => json({ persons: [], parent_child: [], partnerships: [] }),
    });
    renderWithProviders(<App />, { route: "/trees/t1" });
    expect(await screen.findByRole("heading", { name: "Родина" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Адміністрування" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Учасники" })).toBeInTheDocument();
  });

  it("hides member management from viewers", async () => {
    mockApi({
      "GET /api/v1/auth/me": () => json(ME),
      "GET /api/v1/trees/t1": () =>
        json({ id: "t1", name: "Родина", description: null, my_role: "viewer" }),
      "GET /api/v1/trees/t1/graph": () => json({ persons: [], parent_child: [], partnerships: [] }),
    });
    renderWithProviders(<App />, { route: "/trees/t1" });
    expect(await screen.findByRole("heading", { name: "Родина" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Учасники" })).not.toBeInTheDocument();
  });

  it("lets a regular user start their own tree, unless that is turned off", async () => {
    mockApi({
      "GET /api/v1/auth/me": () => json({ ...ME, can_create_trees: true }),
      "GET /api/v1/trees": () => json([]),
    });
    const { unmount } = renderWithProviders(<App />);
    expect(await screen.findByText(/Створіть власний/)).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Новий родовід" }).length).toBeGreaterThan(0);
    unmount();

    mockApi({ "GET /api/v1/auth/me": () => json(ME), "GET /api/v1/trees": () => json([]) });
    renderWithProviders(<App />);
    expect(await screen.findByText(/Попросіть адміністратора/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Новий родовід" })).not.toBeInTheDocument();
  });

  it("keeps non-superadmins out of the admin area", async () => {
    mockApi({ "GET /api/v1/auth/me": () => json(ME), "GET /api/v1/trees": () => json([]) });
    renderWithProviders(<App />, { route: "/admin/users" });
    expect(await screen.findByRole("heading", { name: "Родоводи" })).toBeInTheDocument();
  });

  it("applies the user's preferred language", async () => {
    mockApi({
      "GET /api/v1/auth/me": () => json({ ...ME, preferred_language: "pl" }),
      "GET /api/v1/trees": () => json([]),
    });
    renderWithProviders(<App />);
    await waitFor(() => expect(i18n.language).toBe("pl"));
    expect(await screen.findByRole("heading", { name: "Drzewa rodzinne" })).toBeInTheDocument();
  });

  it("accepts an invitation", async () => {
    let accepted: unknown;
    mockApi({
      ...loggedOut,
      "GET /api/v1/auth/invitations/tok": () =>
        json({
          email: "new@example.com",
          tree_name: "Родина",
          role: "editor",
          is_superadmin: false,
          expires_at: "2030-01-01T00:00:00Z",
        }),
      "POST /api/v1/auth/invitations/tok/accept": (init) => {
        accepted = JSON.parse(String(init.body));
        return json({ status: "ok", user: ME });
      },
      "GET /api/v1/trees": () => json([]),
    });
    renderWithProviders(<App />, { route: "/invite/tok" });
    expect(await screen.findByText(/«Родина» з роллю «Редактор»/)).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Ім’я для відображення"), "Нова людина");
    await userEvent.type(screen.getByLabelText("Новий пароль"), "long-password-1");
    await userEvent.type(screen.getByLabelText("Повторіть пароль"), "long-password-2");
    expect(screen.getByText("Паролі не збігаються.")).toBeInTheDocument();
    await userEvent.clear(screen.getByLabelText("Повторіть пароль"));
    await userEvent.type(screen.getByLabelText("Повторіть пароль"), "long-password-1");
    await userEvent.click(screen.getByRole("button", { name: "Створити обліковий запис" }));
    await waitFor(() =>
      expect(accepted).toEqual({
        display_name: "Нова людина",
        password: "long-password-1",
        preferred_language: "uk",
      }),
    );
  });

  it("shows an error for an invalid invitation link", async () => {
    mockApi({
      ...loggedOut,
      "GET /api/v1/auth/invitations/bad": () => json({ code: "link_invalid" }, 404),
    });
    renderWithProviders(<App />, { route: "/invite/bad" });
    expect(await screen.findByRole("alert")).toHaveTextContent("Посилання недійсне");
  });

  it("shows not-found page for unknown routes", async () => {
    mockApi(loggedOut);
    renderWithProviders(<App />, { route: "/does-not-exist" });
    expect(await screen.findByText("Сторінку не знайдено")).toBeInTheDocument();
  });
});

describe("safeNext", () => {
  it("only allows relative same-site paths", () => {
    expect(safeNext("/trees/1")).toBe("/trees/1");
    expect(safeNext("//evil.example")).toBe("/");
    expect(safeNext("https://evil.example")).toBe("/");
    expect(safeNext("/\\evil.example")).toBe("/");
    expect(safeNext(null)).toBe("/");
  });
});
