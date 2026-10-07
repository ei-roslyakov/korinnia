import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";

import i18n from "@/i18n";
import { applyTheme, readTheme } from "@/lib/theme";

import { ThemeSwitcher } from "./ThemeSwitcher";

beforeEach(async () => {
  await i18n.changeLanguage("uk");
  localStorage.clear();
  delete document.documentElement.dataset.theme;
});

describe("themes", () => {
  it("switches the theme on <html> and remembers it", async () => {
    render(<ThemeSwitcher />);
    const select = screen.getByRole("combobox", { name: "Тема" });
    expect(select).toHaveValue("system");
    expect(screen.getAllByRole("option").map((o) => o.textContent)).toEqual([
      "Як у системі",
      "Світла",
      "Темна",
      "Архівна",
    ]);

    await userEvent.selectOptions(select, "dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(localStorage.getItem("korinnia.theme")).toBe("dark");

    await userEvent.selectOptions(select, "sepia");
    expect(document.documentElement.dataset.theme).toBe("sepia");

    // "System" forgets the choice and follows the device (light in jsdom).
    await userEvent.selectOptions(select, "system");
    expect(localStorage.getItem("korinnia.theme")).toBeNull();
    expect(document.documentElement.dataset.theme).toBe("light");
  });

  it("applies the stored theme at start-up and ignores unknown values", () => {
    localStorage.setItem("korinnia.theme", "sepia");
    applyTheme();
    expect(document.documentElement.dataset.theme).toBe("sepia");
    localStorage.setItem("korinnia.theme", "neon");
    expect(readTheme()).toBe("system");
  });
});
