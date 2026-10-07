import { expect, test, type Page } from "@playwright/test";

const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL ?? "admin@example.com";
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? "change-me-now-please";

async function openDemoTreeInBuilder(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Електронна пошта").fill(ADMIN_EMAIL);
  await page.getByLabel("Пароль").fill(ADMIN_PASSWORD);
  await page.getByRole("button", { name: "Увійти" }).click();
  await page.getByRole("link", { name: /Родина Коваленків \(демо\)/ }).click();
  await page.getByRole("button", { name: "Редагування" }).click();
  await expect(page.getByRole("button", { name: "+ Додати людину" })).toBeVisible();
}

test("builder: add a child from a card, edit, delete and restore", async ({ page }, testInfo) => {
  const name = `Тарас${testInfo.project.name === "mobile" ? "М" : "Д"}${Date.now() % 100000}`;
  await openDemoTreeInBuilder(page);

  // Find Андрій Володимирович (search centres the canvas on him), then "+" below → add child.
  await page.getByRole("combobox", { name: /Знайти людину/ }).fill("Андрій Володимирович");
  await page.getByRole("option", { name: /Андрій Володимирович/ }).click();
  await page.getByRole("button", { name: "Закрити" }).click();
  const card = page.getByTestId("person-card").filter({ hasText: "Андрій Володимирович" });
  await card.getByRole("button", { name: "Додати дитину" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByLabel("Прізвище", { exact: true })).toHaveValue("Коваленко");
  await dialog.getByLabel("Ім’я").fill(name);
  await dialog.getByLabel("Інший з батьків").selectOption({ label: "Оксана Коваленко (Литвин)" });
  await dialog.getByLabel("Народження: точність").selectOption("year");
  await dialog.getByLabel("Народження: Рік").fill("2005");
  await dialog.getByRole("button", { name: "Створити" }).click();

  // The new person is on the canvas and opened in the panel, with both parents.
  const panel = page.getByRole("complementary");
  await expect(panel.getByRole("heading", { name: `${name} Коваленко` })).toBeVisible();
  await expect(panel.getByRole("link", { name: /Андрій Володимирович/ })).toBeVisible();
  await expect(panel.getByRole("link", { name: /Оксана Коваленко/ })).toBeVisible();
  await expect(page.getByTestId("person-card").filter({ hasText: name })).toBeVisible();

  // Edit: occupation + biography (Markdown preview).
  await panel.getByRole("link", { name: "Редагувати" }).click();
  await page.getByLabel("Заняття").fill("Студент");
  await page.getByLabel("Біографія").fill("## Дитинство\n\nНародився в **Києві**.");
  await page.getByRole("tab", { name: "Перегляд" }).first().click();
  await expect(page.getByRole("heading", { name: "Дитинство" })).toBeVisible();
  await page.getByRole("button", { name: "Зберегти" }).click();
  await expect(page.getByText("Збережено.")).toBeVisible();

  // History shows the edit.
  await page.getByRole("tab", { name: "Історія" }).click();
  await expect(page.getByText(/Змінено: .*заняття/)).toBeVisible();

  // Delete with preview → trash → restore.
  await page.getByRole("button", { name: "Видалити" }).click();
  await expect(page.getByRole("dialog").getByText("Зв’язки з батьками: 2")).toBeVisible();
  await page.getByRole("button", { name: "Перемістити до кошика" }).click();
  await expect(page.getByTestId("person-card").filter({ hasText: name })).toHaveCount(0);
  await page.getByRole("link", { name: "Кошик" }).click();
  const item = page.locator("li").filter({ hasText: name });
  await item.getByRole("button", { name: "Відновити" }).click();
  await expect(item).toHaveCount(0);
  await page.getByRole("link", { name: /До дерева/ }).click();
  await expect(page.getByTestId("person-card").filter({ hasText: name })).toBeVisible();
});

test("builder: dragging moves the whole branch and is remembered", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name === "mobile", "mouse drag on desktop");
  // Own tree, so parallel tests editing the demo tree cannot shift the layout mid-drag.
  await page.goto("/login");
  await page.getByLabel("Електронна пошта").fill(ADMIN_EMAIL);
  await page.getByLabel("Пароль").fill(ADMIN_PASSWORD);
  await page.getByRole("button", { name: "Увійти" }).click();
  await expect(page.getByRole("heading", { name: "Родоводи" })).toBeVisible();
  const csrf = (await page.context().cookies()).find((c) => c.name === "korinnia_csrf")!.value;
  const post = async (path: string, data: unknown) => {
    const resp = await page.request.post(path, { data, headers: { "X-CSRF-Token": csrf } });
    expect(resp.ok()).toBe(true);
    return resp.json();
  };
  const tree = await post("/api/v1/trees", { name: `E2E drag ${Date.now()}` });
  const base = `/api/v1/trees/${tree.id}`;
  const parent = await post(`${base}/persons`, { names: [{ first_name: "Батько" }] });
  const child = await post(`${base}/persons`, {
    names: [{ first_name: "Донька" }],
    relative: { person_id: parent.id, relation: "child" },
  });

  await page.goto(`/trees/${tree.id}?mode=edit`);
  // Drag the parent: the branch (the daughter above) moves with it.
  const node = page.locator(`.react-flow__node-person[data-id="${parent.id}"]`);
  const childNode = page.locator(`.react-flow__node-person[data-id="${child.id}"]`);
  await expect(node).toBeVisible();
  // Wait for fit-to-view to finish: the viewport must stay unchanged across 300 ms.
  const viewport = page.locator(".react-flow__viewport");
  for (let stable = 0; stable < 2;) {
    const a = await viewport.getAttribute("style");
    await page.waitForTimeout(300);
    stable = a === (await viewport.getAttribute("style")) ? stable + 1 : 0;
  }
  // Compare positions only: React Flow toggles `visibility` while it measures cards.
  const positionOf = async (n: typeof node) =>
    /translate\([^)]*\)/.exec((await n.getAttribute("style")) ?? "")?.[0];
  const position = () => positionOf(node);
  const before = await position();
  const childBefore = await positionOf(childNode);
  const box = (await node.boundingBox())!;
  const cx = box.x + box.width / 2;
  const cy = box.y + box.height / 2;
  await page.mouse.move(cx, cy);
  await page.mouse.down();
  await page.mouse.move(cx + 120, cy + 60, { steps: 8 });
  await page.mouse.up();
  await expect.poll(position).not.toBe(before);

  // Both cards moved, sideways and down, and are stored as offsets from the automatic layout...
  const offsets = async () =>
    (await (await page.request.get(`${base}/graph`)).json()).layout_offsets ?? {};
  await expect.poll(async () => (await offsets())[child.id]?.dx ?? 0).toBeGreaterThan(50);
  const saved = await offsets();
  expect(saved[parent.id].dx).toBeGreaterThan(50);
  expect(saved[parent.id].dy).toBeGreaterThan(20);
  expect(saved[child.id].dy).toBe(saved[parent.id].dy);
  expect(await positionOf(childNode)).not.toBe(childBefore);
  const moved = await position();

  // ...the card is still there after a reload...
  await page.reload();
  await expect.poll(position).toBe(moved);

  // ...and "Reset layout" puts it back.
  page.once("dialog", (d) => void d.accept());
  await page.getByRole("button", { name: "Скинути розташування" }).click();
  await expect.poll(position).toBe(before);
});
