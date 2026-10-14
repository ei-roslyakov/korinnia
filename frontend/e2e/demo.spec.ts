import { expect, test, type Browser } from "@playwright/test";

import { closeSignInPopups } from "./popups";

// Link names include the people count, so match the tree name only.
const DEMO_TREE = /Родина Коваленків \(демо\)/;

async function startDemo(browser: Browser) {
  const page = await (await browser.newContext()).newPage();
  await closeSignInPopups(page);
  await page.goto("/login");
  await page.getByRole("button", { name: "Спробувати демо" }).click();
  // Creating the demo family takes a few seconds on a fresh server.
  await expect(page.getByText(/Демо · залишилось (29|30):/)).toBeVisible({ timeout: 30_000 });
  return page;
}

test("every demo sign-in gets its own fresh copy of the demo family", async ({ browser }) => {
  const first = await startDemo(browser);
  await first.getByRole("link", { name: DEMO_TREE }).click();
  await expect(first.getByTestId("person-card").first()).toBeVisible();

  // The first visitor renames their copy…
  const treeId = first.url().match(/\/trees\/([0-9a-f-]+)/)![1]!;
  const csrf = (await first.context().cookies()).find((c) => c.name === "korinnia_csrf")!.value;
  const renamed = await first.request.patch(`/api/v1/trees/${treeId}`, {
    data: { name: "Змінено першим відвідувачем" },
    headers: { "X-CSRF-Token": csrf },
  });
  expect(renamed.ok()).toBe(true);

  // …and a second visitor with the same demo login does not see it.
  const second = await startDemo(browser);
  await expect(second.getByRole("link", { name: DEMO_TREE })).toBeVisible();
  await expect(second.getByText("Змінено першим відвідувачем")).toHaveCount(0);

  // Demo accounts cannot share their tree.
  await expect(second.getByRole("button", { name: /Поділитися/ })).toHaveCount(0);
});
