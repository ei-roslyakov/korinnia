import { expect, test } from "@playwright/test";

import { closeSignInPopups } from "./popups";

const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL ?? "admin@example.com";
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? "change-me-now-please";
const DEMO_TREE = "Родина Коваленків (демо)";

test.beforeEach(async ({ page }) => {
  await closeSignInPopups(page);
});

test("a share link opens the tree read-only for someone without an account", async ({
  page,
  browser,
}) => {
  await page.goto("/login");
  await page.getByLabel("Електронна пошта").fill(ADMIN_EMAIL);
  await page.getByLabel("Пароль").fill(ADMIN_PASSWORD);
  await page.getByRole("button", { name: "Увійти" }).click();
  await page.getByRole("link", { name: /Родина Коваленків \(демо\)/ }).click();
  const treeId = page.url().match(/\/trees\/([0-9a-f-]+)/)![1]!;
  const csrf = (await page.context().cookies()).find((c) => c.name === "korinnia_csrf")!.value;
  const headers = { "X-CSRF-Token": csrf };
  const created = await page.request.post(`/api/v1/trees/${treeId}/share-links`, {
    data: { label: "E2E", expires_in_days: 1 },
    headers,
  });
  expect(created.ok()).toBe(true);
  const { url, link } = (await created.json()) as { url: string; link: { id: string } };
  const path = new URL(url).pathname;

  // A different browser, never signed in.
  const guest = await (await browser.newContext()).newPage();
  await guest.goto(path);
  await expect(guest.getByRole("heading", { name: DEMO_TREE })).toBeVisible();
  await expect(guest.getByText("Перегляд за посиланням")).toBeVisible();
  await expect(guest.getByTestId("person-card").first()).toBeVisible();
  await expect(guest.getByRole("button", { name: "Редагування" })).toHaveCount(0);
  // Editing is refused by the server too.
  const edit = await guest.request.patch(`/api/v1/trees/${treeId}`, { data: { name: "X" } });
  expect(edit.status()).toBeGreaterThanOrEqual(400);

  // Revoked: the same browser is asked to sign in.
  await page.request.delete(`/api/v1/trees/${treeId}/share-links/${link.id}`, { headers });
  await guest.reload();
  await expect(guest.getByRole("button", { name: "Увійти" })).toBeVisible();
});
