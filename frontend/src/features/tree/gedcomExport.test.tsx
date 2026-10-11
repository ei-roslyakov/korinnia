import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";

import i18n from "@/i18n";

import { GedcomExportDialog } from "./GedcomExportDialog";

beforeEach(async () => {
  await i18n.changeLanguage("uk");
});

describe("GEDCOM export dialog", () => {
  it("downloads the whole tree, or without the details of living people", async () => {
    render(<GedcomExportDialog treeId="t1" onClose={() => undefined} />);
    const link = screen.getByRole("link", { name: "Завантажити .ged" });
    expect(link).toHaveAttribute("href", "/api/v1/trees/t1/export/gedcom");
    expect(link).toHaveAttribute("download");
    await userEvent.click(screen.getByRole("checkbox", { name: /Не включати дані живих людей/ }));
    expect(link).toHaveAttribute("href", "/api/v1/trees/t1/export/gedcom?living=false");
  });
});
