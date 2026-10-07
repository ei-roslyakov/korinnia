import { expect, test, type Page } from "@playwright/test";

const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL ?? "admin@example.com";
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? "change-me-now-please";

async function openDemoTree(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Електронна пошта").fill(ADMIN_EMAIL);
  await page.getByLabel("Пароль").fill(ADMIN_PASSWORD);
  await page.getByRole("button", { name: "Увійти" }).click();
  await page.getByRole("link", { name: /Родина Коваленків \(демо\)/ }).click();
}

const nav = (page: Page) => page.getByRole("navigation", { name: "Розділи родоводу" });

test("relationship calculator names the kinship", async ({ page }) => {
  await openDemoTree(page);
  await nav(page).getByRole("link", { name: "Спорідненість" }).click();
  const [a, b] = [
    page.getByRole("combobox", { name: "Знайти людину…" }).first(),
    page.getByRole("combobox", { name: "Знайти людину…" }).last(),
  ];
  await a.fill("Андрій");
  await page.getByRole("option", { name: /Андрій Володимирович Коваленко/ }).click();
  await b.fill("Микола");
  await page.getByRole("option", { name: /Микола Федорович Ткач/ }).click();
  // Mykola is a first cousin of Andrii's grandfather Oleksandr.
  await expect(page.getByTestId("kinship-term")).toHaveText("троюрідний дід");
  await expect(page.getByRole("link", { name: /Степан Коваленко/ }).first()).toBeVisible();
  await page.getByRole("button", { name: "Поміняти місцями" }).click();
  await expect(page.getByTestId("kinship-term")).toHaveText("троюрідний онук");
});

test("timeline, on this day, statistics and map", async ({ page }) => {
  await openDemoTree(page);
  await nav(page).getByRole("link", { name: "Хронологія" }).click();
  await expect(page.getByRole("heading", { name: "1860-ті" })).toBeVisible();
  await expect(page.getByText("Шлюб").first()).toBeVisible();

  await page.goto(page.url().replace(/\/timeline.*/, "/on-this-day?date=2025-11-02"));
  // Stepan died on 2 November 1931.
  await expect(page.getByText("94 роки тому")).toBeVisible();
  await expect(page.getByRole("link", { name: "Степан Коваленко" })).toBeVisible();

  await page.goto(page.url().replace(/\/on-this-day.*/, "/stats"));
  await expect(page.getByRole("heading", { name: "Статистика" })).toBeVisible();
  await expect(page.getByText(/^Коваленко/).first()).toBeVisible();
  await expect(page.getByText("Поколінь")).toBeVisible();

  await page.goto(page.url().replace(/\/stats.*/, "/map"));
  await page
    .getByRole("button", { name: /Великі Сорочинці/ })
    .first()
    .click();
  await expect(page.getByRole("heading", { name: "Великі Сорочинці" })).toBeVisible();
  await expect(page.getByText("Народження").first()).toBeVisible();
  // Leaflet drew the markers.
  await expect(page.locator(".leaflet-interactive").first()).toBeVisible();
});
