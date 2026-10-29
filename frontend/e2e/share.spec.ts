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

test("share-link visitors see only the basics of living people", async ({
  page,
  browser,
}, testInfo) => {
  await page.goto("/login");
  await page.getByLabel("Електронна пошта").fill(ADMIN_EMAIL);
  await page.getByLabel("Пароль").fill(ADMIN_PASSWORD);
  await page.getByRole("button", { name: "Увійти" }).click();
  await expect(page.getByRole("link", { name: /Родина Коваленків \(демо\)/ })).toBeVisible();
  const csrf = (await page.context().cookies()).find((c) => c.name === "korinnia_csrf")!.value;
  const headers = { "X-CSRF-Token": csrf };
  // A tree of its own, so changing its settings cannot disturb other tests.
  const name = `Приватність ${testInfo.project.name} ${Date.now()}`;
  const tree = (await (
    await page.request.post("/api/v1/trees", { data: { name }, headers })
  ).json()) as { id: string };
  const person = (await (
    await page.request.post(`/api/v1/trees/${tree.id}/persons`, {
      data: {
        names: [{ first_name: "Олена", last_name: "Коваленко" }],
        birth: { date: { year: 1990, month: 4, day: 2 } },
        biography: "Працює лікаркою.",
      },
      headers,
    })
  ).json()) as { id: string; is_living: boolean };
  expect(person.is_living).toBe(true);
  const created = await page.request.post(`/api/v1/trees/${tree.id}/share-links`, {
    data: { label: "E2E", expires_in_days: 1 },
    headers,
  });
  const { url } = (await created.json()) as { url: string };

  // The admin's dialog tells what visitors will see.
  await page.reload();
  await page.getByRole("button", { name: `Поділитися родоводом «${name}»` }).click();
  await expect(page.getByTestId("share-links-privacy")).toContainText(
    "Відвідувачі бачать лише ім’я, рік народження",
  );
  await page.keyboard.press("Escape");

  const guest = await (await browser.newContext()).newPage();
  await guest.goto(new URL(url).pathname);
  await expect(guest.getByTestId("person-card").first()).toBeVisible();
  await guest.goto(`/trees/${tree.id}/people/${person.id}`);
  await expect(guest.getByTestId("details-hidden")).toBeVisible();
  await expect(guest.getByText("Працює лікаркою.")).toHaveCount(0);

  // The admin turns it off on the Members page: the visitor sees everything.
  await page.goto(`/trees/${tree.id}/members`);
  await page.getByRole("radio", { name: /Ніхто/ }).check();
  const form = page.getByRole("form", { name: "Приватність живих людей" });
  await form.getByRole("button", { name: "Зберегти" }).click();
  await expect(form.getByText("Збережено.")).toBeVisible();
  await guest.reload();
  await expect(guest.getByText("Працює лікаркою.")).toBeVisible();
  await expect(guest.getByTestId("details-hidden")).toHaveCount(0);

  await page.request.delete(`/api/v1/trees/${tree.id}`, { headers });
});
