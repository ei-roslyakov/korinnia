import { expect, test, type Browser, type Page } from "@playwright/test";

const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL ?? "admin@example.com";
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? "change-me-now-please";

async function login(page: Page, email: string, password: string) {
  await page.goto("/login");
  await page.getByLabel("Електронна пошта").fill(email);
  await page.getByLabel("Пароль").fill(password);
  await page.getByRole("button", { name: "Увійти" }).click();
  await expect(page.getByRole("heading", { name: "Родоводи" })).toBeVisible();
}

/** A contributor account and a fresh person, so parallel runs never touch the same records. */
async function setup(browser: Browser, admin: Page, tag: string) {
  const csrf = (await admin.context().cookies()).find((c) => c.name === "korinnia_csrf")!.value;
  const headers = { "X-CSRF-Token": csrf };
  const email = `contrib-${tag}@example.com`;
  const password = "contributor-pass-123";
  const user = await (
    await admin.request.post("/api/v1/admin/users", {
      data: { email, display_name: `Дописувач ${tag}`, password },
      headers,
    })
  ).json();
  const trees = await (await admin.request.get("/api/v1/trees")).json();
  const tree = trees.find((t: { name: string }) => t.name.includes("демо"));
  const resp = await admin.request.post(`/api/v1/trees/${tree.id}/members`, {
    data: { email: user.email, role: "contributor" },
    headers,
  });
  expect(resp.status()).toBe(201);
  const person = await (
    await admin.request.post(`/api/v1/trees/${tree.id}/persons`, {
      data: {
        names: [{ first_name: "Микола", last_name: `Ткач ${tag}`, is_primary: true }],
        gender: "male",
        occupation: "Тракторист",
        birth: { date: { year: 1931 } },
      },
      headers,
    })
  ).json();
  const page = await (await browser.newContext()).newPage();
  await login(page, email, password);
  return { contributor: page, personUrl: `/trees/${tree.id}/people/${person.id}` };
}

test("contributor suggests and writes; editor approves, publishes and cites", async ({
  page: admin,
  browser,
}, testInfo) => {
  const tag = `${testInfo.project.name}${testInfo.repeatEachIndex}-${Date.now() % 100000}`;
  await login(admin, ADMIN_EMAIL, ADMIN_PASSWORD);
  const { contributor, personUrl } = await setup(browser, admin, tag);

  // Contributor: suggest an edit to Mykola and write a story.
  await contributor.goto(personUrl);
  await contributor.getByRole("button", { name: "Запропонувати зміну" }).click();
  const dialog = contributor.getByRole("dialog");
  await dialog.getByLabel("Заняття").fill(`Агроном ${tag}`);
  await dialog.getByLabel(/Звідки ця інформація/).fill("Трудова книжка");
  await dialog.getByRole("button", { name: "Надіслати пропозицію" }).click();
  await expect(dialog.getByText(/Пропозицію надіслано/)).toBeVisible();
  await dialog.getByRole("button", { name: "Готово" }).click();
  await contributor.getByRole("textbox", { name: "Додати коментар" }).fill(`Коментар ${tag}`);
  await contributor.getByRole("button", { name: "Додати коментар" }).click();
  await expect(contributor.getByText(`Коментар ${tag}`)).toBeVisible();

  await contributor.goto(contributor.url().replace(/\/people\/.*/, "/stories/new"));
  await contributor.getByLabel("Назва").fill(`Історія ${tag}`);
  await contributor
    .getByLabel("Історія", { exact: true })
    .fill(`Він вирощував найкращі помідори в селі (${tag}).`);
  await contributor.getByRole("button", { name: "Надіслати на перевірку" }).click();
  await expect(contributor.getByText("На перевірці").first()).toBeVisible();

  // Editor: moderation queue → approve suggestion, publish story.
  await admin.goto(personUrl.replace(/\/people\/.*/, "/moderation"));
  // Each suggestion is a Card (<section>) inside the queue's <section>.
  const card = admin.locator("section section").filter({ hasText: `Агроном ${tag}` });
  await card.getByRole("button", { name: "Схвалити й застосувати" }).click();
  await expect(admin.getByText(`Агроном ${tag}`)).toHaveCount(0);
  await admin.getByRole("link", { name: `Історія ${tag}` }).click();
  await admin.getByRole("button", { name: "Опублікувати" }).click();
  await expect(admin.getByText("На перевірці")).toHaveCount(0);

  // The contributor's change is live; the story is published for everyone.
  await contributor.goto(contributor.url().replace(/\/stories\/.*/, "/stories"));
  await expect(contributor.getByRole("link", { name: `Історія ${tag}` })).toBeVisible();
  await contributor.getByRole("link", { name: `Історія ${tag}` }).click();
  await expect(contributor.getByText(`помідори в селі (${tag})`)).toBeVisible();

  // Editor cites a source for Mykola's birth; it shows on his page with the new occupation.
  await admin.goto(personUrl);
  await expect(admin.getByText(`Агроном ${tag}`)).toBeVisible();
  await admin.goto(`${personUrl}/edit`);
  await admin.getByRole("tab", { name: "Джерела" }).click();
  await admin.getByRole("button", { name: "+ Послатися на джерело" }).click();
  const cite = admin.getByRole("dialog", { name: "Послатися на джерело" });
  await cite.getByLabel("Що підтверджує").selectOption({
    label: await cite
      .getByRole("option", { name: /^Народження/ })
      .first()
      .innerText(),
  });
  await cite.getByLabel("Пошук джерел…").fill(`Метрика ${tag}`);
  await cite.getByRole("button", { name: "+ Нове джерело" }).click();
  await admin
    .getByRole("dialog", { name: "Нове джерело" })
    .getByRole("button", { name: "Зберегти" })
    .click();
  // The citation dialog is inert until the new-source dialog on top of it closes.
  await expect(admin.getByRole("dialog", { name: "Нове джерело" })).toHaveCount(0);
  await expect(cite.getByText(`Метрика ${tag}`)).toBeVisible();
  await cite.getByLabel("Сторінка / аркуш").fill("арк. 7");
  await cite.getByRole("button", { name: "Зберегти" }).click();
  await expect(admin.getByText(/Народження/).first()).toBeVisible();
  await admin.getByRole("link", { name: "Переглянути сторінку" }).click();
  const sources = admin
    .locator("section")
    .filter({ has: admin.getByRole("heading", { name: "Джерела" }) });
  await expect(sources.getByText(`Метрика ${tag}`)).toBeVisible();
  await expect(sources.getByText("арк. 7")).toBeVisible();
});

test("data quality page lists research to-dos", async ({ page }) => {
  await login(page, ADMIN_EMAIL, ADMIN_PASSWORD);
  await page.getByRole("link", { name: /Родина Коваленків \(демо\)/ }).click();
  await page.getByRole("link", { name: "Якість даних" }).click();
  await expect(page.getByRole("heading", { name: "Якість даних" })).toBeVisible();
  await expect(page.getByText(/Список дослідницьких завдань для \d+ людей/)).toBeVisible();
  await expect(page.getByRole("heading", { name: /Без джерел \(\d+\)/ })).toBeVisible();
});
