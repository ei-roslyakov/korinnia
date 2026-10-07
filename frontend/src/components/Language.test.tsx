import { screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "@/App";
import i18n, { DEFAULT_LANGUAGE } from "@/i18n";
import { json, ME, mockApi } from "@/test/mockApi";
import { renderWithProviders } from "@/test/render";

afterEach(() => vi.unstubAllGlobals());

describe("default language", () => {
  it("is English until the server says otherwise", () => {
    expect(DEFAULT_LANGUAGE).toBe("en");
  });

  it("follows the installation default for visitors who never chose one", async () => {
    await i18n.changeLanguage("en");
    mockApi({
      "GET /api/v1/auth/me": () => json({ code: "not_authenticated" }, 401),
      "POST /api/v1/auth/refresh": () => json({ code: "not_authenticated" }, 401),
      "GET /api/v1/meta": () =>
        json({ name: "Korinnia", version: "1", environment: "test", default_language: "pl" }),
    });
    renderWithProviders(<App />, { route: "/login" });
    expect(await screen.findByLabelText("Hasło")).toBeInTheDocument();
  });

  it("uses the signed-in user's own language over the installation default", async () => {
    await i18n.changeLanguage("en");
    mockApi({
      "GET /api/v1/auth/me": () => json({ ...ME, preferred_language: "uk" }),
      "GET /api/v1/trees": () => json([]),
      "GET /api/v1/meta": () =>
        json({ name: "Korinnia", version: "1", environment: "test", default_language: "pl" }),
    });
    renderWithProviders(<App />, { route: "/" });
    await waitFor(() => expect(i18n.resolvedLanguage).toBe("uk"));
    expect(await screen.findByRole("heading", { name: "Родоводи" })).toBeInTheDocument();
  });
});
