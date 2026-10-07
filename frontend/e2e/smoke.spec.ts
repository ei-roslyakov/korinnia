import { expect, test } from "@playwright/test";

const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL ?? "admin@example.com";
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? "change-me-now-please";

test("security headers are set by nginx", async ({ request }) => {
  const resp = await request.get("/");
  expect(resp.headers()["x-content-type-options"]).toBe("nosniff");
  expect(resp.headers()["content-security-policy"]).toContain("default-src 'self'");
});

test("wrong credentials show a translated error", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/login/);
  await page.getByLabel("Електронна пошта").fill(`nobody-${Date.now()}@example.com`);
  await page.getByLabel("Пароль").fill("definitely-wrong");
  await page.getByRole("button", { name: "Увійти" }).click();
  await expect(page.getByRole("alert")).toHaveText("Неправильна пошта або пароль.");
});

test("admin creates a tree and invites a relative who joins it", async ({ page }, testInfo) => {
  const suffix = `${Date.now()}-${testInfo.project.name}`;
  const treeName = `E2E родина ${suffix}`;
  const guestEmail = `guest-${suffix}@example.com`;

  // Superadmin signs in (bootstrapped from SUPERADMIN_* env vars).
  await page.goto("/login");
  await page.getByLabel("Електронна пошта").fill(ADMIN_EMAIL);
  await page.getByLabel("Пароль").fill(ADMIN_PASSWORD);
  await page.getByRole("button", { name: "Увійти" }).click();
  await expect(page.getByRole("heading", { name: "Родоводи" })).toBeVisible();

  // Create a tree.
  await page.getByRole("button", { name: "Новий родовід" }).click();
  await page.getByLabel("Назва").fill(treeName);
  await page.getByRole("button", { name: "Створити" }).click();
  await page.getByRole("link", { name: new RegExp(treeName) }).click();
  await expect(page.getByRole("heading", { name: treeName })).toBeVisible();

  // Invite a new relative as editor.
  await page.getByRole("link", { name: "Учасники" }).click();
  await page.getByLabel("Електронна пошта").fill(guestEmail);
  await page.getByLabel("Роль").first().selectOption("editor");
  await page.getByRole("button", { name: "Додати" }).click();
  const link = await page.getByRole("textbox", { name: "Посилання" }).inputValue();
  expect(link).toContain("/invite/");
  await expect(page.getByText(guestEmail)).toBeVisible();

  // Sign out; the relative opens the link and creates an account.
  await page.getByRole("button", { name: "Вийти" }).click();
  await expect(page).toHaveURL(/\/login/);
  await page.goto(new URL(link).pathname);
  await expect(page.getByText(`«${treeName}» з роллю «Редактор»`)).toBeVisible();
  await page.getByLabel("Ім’я для відображення").fill("Тестовий родич");
  await page.getByLabel("Новий пароль").fill("a-long-e2e-password");
  await page.getByLabel("Повторіть пароль").fill("a-long-e2e-password");
  await page.getByRole("button", { name: "Створити обліковий запис" }).click();

  // They land on their tree list with the editor role and no admin access.
  await expect(page.getByRole("heading", { name: "Родоводи" })).toBeVisible();
  const card = page.getByRole("link", { name: new RegExp(treeName) });
  await expect(card).toContainText("Редактор");
  await expect(page.getByRole("link", { name: "Адміністрування" })).toHaveCount(0);

  // The invitation link cannot be reused.
  await page.getByRole("button", { name: "Вийти" }).click();
  await page.goto(new URL(link).pathname);
  await expect(page.getByRole("alert")).toContainText("Посилання недійсне");
});
