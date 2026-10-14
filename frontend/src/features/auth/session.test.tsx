import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "@/App";
import i18n from "@/i18n";
import { setSessionExpired } from "@/lib/session";
import { formatLeft } from "@/lib/timeLeft";
import { json, ME, mockApi } from "@/test/mockApi";
import { renderWithProviders } from "@/test/render";

const inMinutes = (m: number) => new Date(Date.now() + m * 60_000).toISOString();

beforeEach(async () => {
  await i18n.changeLanguage("uk");
  document.cookie = "korinnia_csrf=csrf-123; path=/";
  setSessionExpired(false);
});
afterEach(() => vi.unstubAllGlobals());

describe("session timeout", () => {
  it("formats the time left", () => {
    expect(formatLeft(90_500)).toBe("1:31");
    expect(formatLeft(-5)).toBe("0:00");
  });

  it("warns before the end and keeps the user signed in", async () => {
    let extended = false;
    mockApi({
      "GET /api/v1/auth/me": () => json({ ...ME, session_expires_at: inMinutes(1) }),
      "GET /api/v1/trees": () => json([]),
      "POST /api/v1/auth/session/extend": () => {
        extended = true;
        return json({ ...ME, session_expires_at: inMinutes(480) });
      },
    });
    renderWithProviders(<App />);
    expect(await screen.findByText(/Сеанс завершиться через \d:\d\d/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Залишитися в системі" }));
    await waitFor(() => expect(extended).toBe(true));
    await waitFor(() =>
      expect(screen.queryByText(/Сеанс завершиться через/)).not.toBeInTheDocument(),
    );
  });

  it("asks for the password again when the session has ended, without leaving the page", async () => {
    let body: unknown;
    let signedIn = false;
    mockApi({
      "GET /api/v1/auth/me": () =>
        json({ ...ME, session_expires_at: inMinutes(signedIn ? 480 : -1) }),
      "GET /api/v1/trees": () => json([]),
      "POST /api/v1/auth/login": (init) => {
        body = JSON.parse(String(init.body));
        signedIn = true;
        return json({ status: "ok", user: { ...ME, session_expires_at: inMinutes(480) } });
      },
    });
    renderWithProviders(<App />, { route: "/profile" });
    const dialog = await screen.findByRole("dialog", { name: "Сеанс завершився" });
    expect(dialog).toHaveTextContent(ME.email);
    await userEvent.type(screen.getByLabelText("Пароль"), "s3cret-password");
    await userEvent.click(screen.getByRole("button", { name: "Оновити сеанс" }));
    await waitFor(() => expect(body).toEqual({ email: ME.email, password: "s3cret-password" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(screen.getByRole("heading", { name: "Ваш профіль" })).toBeInTheDocument();
  });

  it("shows the demo countdown and offers a fresh demo when it ends", async () => {
    let started = false;
    mockApi({
      "GET /api/v1/auth/me": () =>
        json({ ...ME, is_sandbox: true, session_expires_at: inMinutes(-1) }),
      "GET /api/v1/trees": () => json([]),
      "POST /api/v1/auth/demo": () => {
        started = true;
        return json({
          status: "ok",
          user: { ...ME, is_sandbox: true, session_expires_at: inMinutes(30) },
        });
      },
    });
    renderWithProviders(<App />);
    expect(await screen.findByRole("dialog", { name: "Демо завершилося" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Почати нове демо" }));
    await waitFor(() => expect(started).toBe(true));
    expect(await screen.findByText(/Демо · залишилось (29|30):/)).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("offers the demo on the sign-in page when the installation has one", async () => {
    mockApi({
      "GET /api/v1/auth/me": () => json({ code: "not_authenticated" }, 401),
      "POST /api/v1/auth/refresh": () => json({ code: "not_authenticated" }, 401),
      "GET /api/v1/meta": () =>
        json({
          name: "Korinnia",
          version: "dev",
          environment: "dev",
          demo_login: { email: "demo@example.com", password: "demo@example.com" },
        }),
    });
    renderWithProviders(<App />, { route: "/login" });
    expect(await screen.findByRole("button", { name: "Спробувати демо" })).toBeInTheDocument();
    expect(screen.getByText(/demo@example.com \/ demo@example.com/)).toBeInTheDocument();
  });
});
