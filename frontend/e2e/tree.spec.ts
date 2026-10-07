import { expect, test, type Page } from "@playwright/test";

const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL ?? "admin@example.com";
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? "change-me-now-please";
const DEMO_TREE = "Родина Коваленків (демо)"; // created by `python -m app.seed`

async function openDemoTree(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Електронна пошта").fill(ADMIN_EMAIL);
  await page.getByLabel("Пароль").fill(ADMIN_PASSWORD);
  await page.getByRole("button", { name: "Увійти" }).click();
  await page.getByRole("link", { name: new RegExp(DEMO_TREE.replace(/[()]/g, "\\$&")) }).click();
  await expect(page.getByRole("heading", { name: DEMO_TREE })).toBeVisible();
  // Other tests may add people to the shared demo tree in parallel.
  await expect(page.getByText(/Людей: (2[5-9]|3\d)/)).toBeVisible();
}

test("tree canvas: cards, pan, person panel and page", async ({ page }) => {
  await openDemoTree(page);
  const cards = page.getByTestId("person-card");
  await expect(cards.first()).toBeVisible();
  // After fit-to-view the whole demo family is on screen (cards outside the viewport are
  // not rendered at all).
  await expect.poll(() => cards.count()).toBeGreaterThan(20);

  // Dragging the empty canvas pans the view. Wait until fit-to-view has settled, then drag
  // from the top-left corner (the zoom controls live bottom-left).
  const viewport = page.locator(".react-flow__viewport");
  let before = await viewport.getAttribute("style");
  await expect
    .poll(async () => {
      const now = await viewport.getAttribute("style");
      const settled = now === before;
      before = now;
      return settled;
    })
    .toBe(true);
  const box = (await page.locator(".react-flow__pane").boundingBox())!;
  await page.mouse.move(box.x + 15, box.y + 15);
  await page.mouse.down();
  await page.mouse.move(box.x + 135, box.y + 75, { steps: 5 });
  await page.mouse.up();
  await expect.poll(() => viewport.getAttribute("style")).not.toBe(before);

  // Clicking a person opens the panel with the biography.
  await page
    .getByRole("button", { name: "Вмістити на екран" })
    .click()
    .catch(() => undefined);
  await page.getByTestId("person-card").filter({ hasText: "Галина Йосипівна" }).click();
  const panel = page.getByRole("complementary");
  await expect(
    panel.getByRole("heading", { name: "Галина Йосипівна Коваленко (Шевчук)" }),
  ).toBeVisible();
  await expect(panel.getByRole("heading", { name: "Війна" })).toBeVisible();
  await expect(panel.getByText("Івано-Франківськ").first()).toBeVisible();

  // Relatives are links; the full page works.
  await panel.getByRole("link", { name: "Відкрити сторінку" }).click();
  await expect(page).toHaveURL(/\/people\//);
  await expect(
    page.getByRole("heading", { name: "Галина Йосипівна Коваленко (Шевчук)" }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: /Олександр Іванович Коваленко/ })).toBeVisible();
});

test("search by Latin spelling centres and opens the person", async ({ page }) => {
  await openDemoTree(page);
  await page.getByRole("combobox", { name: /Знайти людину/ }).fill("tkachuk");
  const option = page.getByRole("option", { name: /Emily Tkachuk/ });
  await expect(option).toBeVisible();
  await option.click();
  const panel = page.getByRole("complementary");
  await expect(panel.getByRole("heading", { name: "Emily Tkachuk" })).toBeVisible();
  await expect(page).toHaveURL(/person=/);

  // Focus mode around her: only nearby generations stay on the canvas.
  await panel.getByRole("button", { name: "Зосередитися тут" }).click();
  await page.getByLabel("Покоління").selectOption("2");
  // Emily, her father Stephen and his parents Olha & Mykhailo.
  await expect(page.getByTestId("person-card")).toHaveCount(4);
});
