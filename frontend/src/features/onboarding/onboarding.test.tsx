import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "@/App";
import i18n from "@/i18n";
import { json, ME, mockApi } from "@/test/mockApi";
import type { Me } from "@/lib/types";
import { renderWithProviders } from "@/test/render";

import { CHANGELOG, LATEST, unseen } from "./changelog";

beforeEach(async () => {
  await i18n.changeLanguage("uk");
  document.cookie = "korinnia_csrf=x; path=/";
  sessionStorage.clear();
});
afterEach(() => vi.unstubAllGlobals());

function api(me: Partial<Me>) {
  const patches: unknown[] = [];
  mockApi({
    "GET /api/v1/auth/me": () => json({ ...ME, ...me }),
    "GET /api/v1/trees": () => json([]),
    "PATCH /api/v1/auth/me": (init) => {
      const body = JSON.parse(String(init.body)) as Record<string, unknown>;
      patches.push(body);
      return json({ ...ME, ...me, ...body });
    },
  });
  return patches;
}

describe("welcome guide", () => {
  it("greets a new user; 'don't show again' is remembered", async () => {
    const patches = api({ welcome_dismissed: false, changelog_seen: null });
    renderWithProviders(<App />, { route: "/" });
    const dialog = within(
      await screen.findByRole("dialog", { name: "Ласкаво просимо до Коріння" }),
    );
    expect(dialog.getByText("Будуйте.")).toBeInTheDocument();
    await userEvent.click(dialog.getByRole("checkbox", { name: "Більше не показувати" }));
    await userEvent.click(dialog.getByRole("button", { name: "Почати" }));
    await waitFor(() =>
      expect(patches).toEqual([{ welcome_dismissed: true, changelog_seen: LATEST }]),
    );
    // A new user gets no "What's new" on top of the guide.
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("comes back next time unless ticked, and opens from the footer", async () => {
    const patches = api({ welcome_dismissed: false, changelog_seen: null });
    renderWithProviders(<App />, { route: "/" });
    await userEvent.click(await screen.findByRole("button", { name: "Почати" }));
    await waitFor(() =>
      expect(patches).toEqual([{ welcome_dismissed: false, changelog_seen: LATEST }]),
    );
    await userEvent.click(screen.getByRole("button", { name: "Як почати" }));
    expect(await screen.findByRole("dialog", { name: "Ласкаво просимо до Коріння" })).toBeVisible();
  });
});

describe("what's new", () => {
  it("shows only the news since the last visit, once", async () => {
    const patches = api({ changelog_seen: CHANGELOG[1]!.id });
    renderWithProviders(<App />, { route: "/" });
    const dialog = within(await screen.findByRole("dialog", { name: "Що нового" }));
    expect(dialog.getAllByRole("listitem")).toHaveLength(CHANGELOG[0]!.items.uk.length);
    expect(dialog.getByText(/Поділитися родоводом/)).toBeInTheDocument();
    await userEvent.click(
      dialog.getByRole("checkbox", { name: "Не показувати новини під час входу" }),
    );
    await userEvent.click(dialog.getByRole("button", { name: "Зрозуміло" }));
    await waitFor(() =>
      expect(patches).toEqual([{ changelog_seen: LATEST, show_changelog: false }]),
    );
  });

  it("stays quiet when turned off or nothing is new; the footer shows all news", async () => {
    api({ changelog_seen: "2000-01-01", show_changelog: false });
    renderWithProviders(<App />, { route: "/" });
    await userEvent.click(await screen.findByRole("button", { name: "Що нового" }));
    const dialog = within(await screen.findByRole("dialog", { name: "Що нового" }));
    expect(dialog.getAllByRole("heading", { level: 3 })).toHaveLength(CHANGELOG.length);
  });

  it("knows what is unseen", () => {
    expect(unseen(null)).toHaveLength(CHANGELOG.length);
    expect(unseen(LATEST)).toHaveLength(0);
    expect(CHANGELOG.map((e) => e.id)).toEqual([...CHANGELOG.map((e) => e.id)].sort().reverse());
    for (const e of CHANGELOG) expect(e.items.uk.length).toBe(e.items.en.length);
  });
});
