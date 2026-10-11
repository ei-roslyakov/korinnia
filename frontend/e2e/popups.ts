import type { Page } from "@playwright/test";

/**
 * The welcome guide and "What's new" pop up after signing in. Tests that are not about them
 * close them whenever they appear (Playwright waits for this before each action).
 */
export async function closeSignInPopups(page: Page): Promise<void> {
  await page.addLocatorHandler(
    page.getByRole("dialog", { name: /^(Ласкаво просимо до Коріння|Що нового)$/ }),
    async (dialog) => {
      await dialog.getByRole("button", { name: /^(Почати|Зрозуміло)$/ }).click();
    },
  );
}
