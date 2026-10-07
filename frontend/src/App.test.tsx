import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";
import i18n from "./i18n";
import { renderWithProviders } from "./test/render";

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

describe("App", () => {
  beforeEach(async () => {
    await i18n.changeLanguage("uk");
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) =>
        Promise.resolve(
          url.endsWith("/api/v1/meta")
            ? jsonResponse({ name: "Korinnia", version: "0.1.0", environment: "test" })
            : jsonResponse({ status: "error", checks: { database: "ok", storage: "error" } }, 503),
        ),
      ),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders in Ukrainian by default and shows system status", async () => {
    renderWithProviders(<App />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Коріння");
    await waitFor(() => expect(screen.getByText("Версія 0.1.0")).toBeInTheDocument());
    expect(screen.getAllByText("Працює")).toHaveLength(2); // api + database
    expect(screen.getByText("Помилка")).toBeInTheDocument(); // storage (503 body)
  });

  it("switches language", async () => {
    renderWithProviders(<App />);
    await userEvent.selectOptions(screen.getByRole("combobox"), "en");
    expect(screen.getByText("System status")).toBeInTheDocument();
  });

  it("shows not-found page for unknown routes", () => {
    renderWithProviders(<App />, { route: "/does-not-exist" });
    expect(screen.getByText("Сторінку не знайдено")).toBeInTheDocument();
  });
});
