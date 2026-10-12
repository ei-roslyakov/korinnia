import { screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "@/App";
import i18n from "@/i18n";
import { json, ME, mockApi } from "@/test/mockApi";
import { renderWithProviders } from "@/test/render";

import en from "./guide.en.md?raw";
import uk from "./guide.uk.md?raw";
import { slug } from "./slug";

beforeEach(() => {
  document.cookie = "korinnia_csrf=x; path=/";
});
afterEach(() => vi.unstubAllGlobals());

const sections = (text: string) => [...text.matchAll(/^## (.+)$/gm)].map((m) => m[1]);

describe("user guide", () => {
  it("has the same sections in Ukrainian and English", () => {
    expect(sections(uk)).toHaveLength(sections(en).length);
    expect(sections(en).length).toBeGreaterThanOrEqual(10);
    expect(slug("Вхід і ваш профіль")).toBe("вхід-і-ваш-профіль");
  });

  it("shows the guide in the interface language with a table of contents", async () => {
    await i18n.changeLanguage("uk");
    mockApi({ "GET /api/v1/auth/me": () => json(ME) });
    renderWithProviders(<App />, { route: "/help" });
    expect(
      await screen.findByRole("heading", { level: 1, name: "Посібник користувача" }),
    ).toBeVisible();
    const toc = screen.getByRole("navigation", { name: "Зміст" });
    const link = within(toc).getByRole("link", { name: "Будуємо родовід (редактори)" });
    expect(link).toHaveAttribute("href", "#будуємо-родовід-редактори");
    expect(document.getElementById("будуємо-родовід-редактори")).not.toBeNull();
    expect(screen.getByRole("link", { name: "Посібник" })).toHaveAttribute("href", "/help");
  });

  it("falls back to English, and works without signing in", async () => {
    await i18n.changeLanguage("pl");
    mockApi({
      "GET /api/v1/auth/me": () => json({ code: "not_authenticated" }, 401),
      "POST /api/v1/auth/refresh": () => json({ code: "not_authenticated" }, 401),
      "GET /api/v1/meta": () => json({ name: "Korinnia", version: "dev", environment: "dev" }),
    });
    renderWithProviders(<App />, { route: "/help" });
    expect(await screen.findByRole("heading", { level: 1, name: "User guide" })).toBeVisible();
    expect(screen.getByText(/nie jest jeszcze dostępny po polsku/)).toBeVisible();
  });
});
