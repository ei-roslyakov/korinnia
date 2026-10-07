import { screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import i18n from "@/i18n";
import { halyna } from "@/test/fixtures";
import { json, ME, mockApi } from "@/test/mockApi";
import { renderWithProviders } from "@/test/render";

import { PersonView } from "./PersonView";

beforeEach(async () => {
  await i18n.changeLanguage("uk");
  mockApi({
    "GET /api/v1/auth/me": () => json(ME),
    "GET /api/v1/trees/t1/comments": () => json([]),
  });
});
afterEach(() => vi.unstubAllGlobals());

const noBio = { ...halyna, biography: null };
const link = (id: string) => `/trees/t1/people/${id}`;

describe("biography section", () => {
  it("is always shown, with a note when nothing is written yet", () => {
    renderWithProviders(<PersonView person={noBio} personLink={link} />);
    expect(screen.getByRole("heading", { name: "Біографія" })).toBeInTheDocument();
    expect(screen.getByText(/Біографію ще не написано/)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Написати біографію" })).not.toBeInTheDocument();
  });

  it("invites editors to write it and contributors to suggest it", () => {
    const { unmount } = renderWithProviders(
      <PersonView person={noBio} personLink={link} treeId="t1" role="editor" />,
    );
    expect(screen.getByRole("link", { name: "Написати біографію" })).toHaveAttribute(
      "href",
      "/trees/t1/people/p2/edit",
    );
    unmount();
    renderWithProviders(
      <PersonView person={noBio} personLink={link} treeId="t1" role="contributor" />,
    );
    expect(screen.getByRole("button", { name: "Запропонувати біографію" })).toBeInTheDocument();
  });

  it("renders the biography when there is one", () => {
    renderWithProviders(<PersonView person={halyna} personLink={link} />);
    expect(screen.queryByText(/Біографію ще не написано/)).not.toBeInTheDocument();
  });
});
