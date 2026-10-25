import { expect, test, type Page } from "@playwright/test";

import { closeSignInPopups } from "./popups";

test.beforeEach(async ({ page }) => {
  await closeSignInPopups(page);
});

const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL ?? "admin@example.com";
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? "change-me-now-please";

/** A real JPEG drawn in the browser (no binary fixtures in the repo). */
async function makeJpeg(page: Page, label: string): Promise<Buffer> {
  const b64 = await page.evaluate((text) => {
    const c = document.createElement("canvas");
    c.width = 800;
    c.height = 600;
    const g = c.getContext("2d")!;
    g.fillStyle = "#8aa4c8";
    g.fillRect(0, 0, 800, 600);
    g.fillStyle = "#7a5638";
    g.fillRect(200, 150, 400, 300);
    g.fillStyle = "#000";
    g.font = "32px sans-serif";
    g.fillText(text, 40, 560);
    return c.toDataURL("image/jpeg", 0.9).split(",")[1]!;
  }, label);
  return Buffer.from(b64, "base64");
}

test("a described photo shows in the family album on the tree page and the album page", async ({
  page,
}, testInfo) => {
  await page.goto("/login");
  await page.getByLabel("Електронна пошта").fill(ADMIN_EMAIL);
  await page.getByLabel("Пароль").fill(ADMIN_PASSWORD);
  await page.getByRole("button", { name: "Увійти" }).click();
  await expect(page.getByRole("link", { name: /Родина Коваленків \(демо\)/ })).toBeVisible();

  // Unique per run, so parallel projects never see each other's photo as theirs.
  const tag = `${testInfo.project.name}-${testInfo.repeatEachIndex}-${Date.now() % 1000000}`;
  const surname = `Альбом${testInfo.project.name.length}${Date.now() % 1000000}`;
  const description = `Пікнік над Дніпром ${tag}`;
  const trees = await (await page.request.get("/api/v1/trees")).json();
  const treeId = trees.find((t: { name: string }) => t.name.includes("демо")).id;
  const csrf = (await page.context().cookies()).find((c) => c.name === "korinnia_csrf")!.value;
  const created = await page.request.post(`/api/v1/trees/${treeId}/persons`, {
    data: { names: [{ first_name: "Ольга", last_name: surname, is_primary: true }] },
    headers: { "X-CSRF-Token": csrf },
  });
  expect(created.status()).toBe(201);
  const personId = (await created.json()).id;
  const brother = await page.request.post(`/api/v1/trees/${treeId}/persons`, {
    data: { names: [{ first_name: "Петро", last_name: surname, is_primary: true }] },
    headers: { "X-CSRF-Token": csrf },
  });
  expect(brother.status()).toBe(201);

  // 1. The editor uploads a photo, describes it right away and adds who else is in it.
  await page.goto(`/trees/${treeId}/people/${personId}/edit?tab=media`);
  await page.getByLabel("Вибрати файли").setInputFiles({
    name: `album-${tag}.jpg`,
    mimeType: "image/jpeg",
    buffer: await makeJpeg(page, tag),
  });
  const dialog = page.getByRole("dialog", { name: "Опишіть фото" });
  await dialog.getByLabel("Опис").fill(description);
  // Older than every demo portrait, so it is among the first photos of the album.
  await dialog.getByLabel("Дата: точність").selectOption("year");
  await dialog.getByLabel("Дата: Рік").fill("1801");
  await dialog
    .getByRole("combobox", { name: "Оберіть людину з родоводу…" })
    .fill(`Петро ${surname}`);
  await page.getByRole("option", { name: new RegExp(`Петро ${surname}`) }).click();
  await expect(
    dialog.getByRole("list", { name: "Хто ще на фото" }).getByText(`Петро ${surname}`),
  ).toBeVisible();
  await dialog.getByRole("button", { name: "Зберегти" }).click();
  await expect(dialog).toHaveCount(0);
  const row = page.locator("li").filter({ hasText: `album-${tag}.jpg` });
  await expect(row.locator("img")).toBeVisible({ timeout: 30_000 });
  await expect(row.getByText("людей: 2")).toBeVisible();

  // 2. It is in the album popup on the tree page (opened with the button), the description
  // above the photo.
  await page.goto(`/trees/${treeId}`);
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.getByRole("button", { name: /Сімейний альбом/ }).click();
  const popup = page.getByRole("dialog", { name: "Сімейний альбом" });
  const album = popup.getByRole("region", { name: "Сімейний альбом" });
  const shown = album.locator('[aria-roledescription="слайд"]:not([inert])');
  const status = album.getByText(/^\d+ з \d+$/);
  const next = album.getByRole("button", { name: "Наступне" });
  await expect(shown).toBeVisible();
  for (let i = 0; i < 10 && !(await shown.textContent())?.includes(description); i++) {
    // 3. Next moves to the following photo.
    const before = await status.textContent();
    await next.click();
    await expect(status).not.toHaveText(before!);
  }
  await expect(shown.getByText(description)).toBeVisible();
  await expect(shown.getByText("1801")).toBeVisible();
  await expect(shown.getByRole("button", { name: new RegExp(`Петро ${surname}`) })).toBeVisible();
  const text = (await shown.getByText(description).boundingBox())!;
  const photo = (await shown.getByRole("img").boundingBox())!;
  expect(text.y + text.height).toBeLessThanOrEqual(photo.y + 1);
  // The person chip offers their page, only their photos, or the tree.
  await shown.getByRole("button", { name: new RegExp(`Ольга ${surname}`) }).click();
  await expect(shown.getByRole("link", { name: "Відкрити сторінку" })).toHaveAttribute(
    "href",
    `/trees/${treeId}/people/${personId}`,
  );
  await shown.getByRole("button", { name: "Лише фото цієї людини" }).click();
  await expect(popup.getByText(`Фото: Ольга ${surname}`)).toBeVisible();
  await expect(status).toHaveText("1 з 1");
  await popup.getByRole("button", { name: "Показати фото всіх" }).click();
  await expect(status).toHaveText(/^1 з \d+$/);
  const before = await status.textContent();
  await next.click();
  await expect(status).not.toHaveText(before!);

  // The album page, filtered to this person: only this photo.
  await popup.getByRole("link", { name: /Показати всі/ }).click();
  await expect(page).toHaveURL(new RegExp(`/trees/${treeId}/album`));
  await page.getByRole("combobox", { name: "Хто на фото" }).fill(surname);
  await page.getByRole("option", { name: new RegExp(`Ольга ${surname}`) }).click();
  await expect(page.getByText("1 фотографія")).toBeVisible();
  const large = page.getByRole("region", { name: "Сімейний альбом" });
  await expect(large.getByText(description)).toBeVisible();
  await page.getByRole("button", { name: "Сітка" }).click();
  await expect(page.getByRole("img", { name: description })).toBeVisible();
});

test("a new place created while describing a photo keeps the editor and the photo", async ({
  page,
}, testInfo) => {
  await page.goto("/login");
  await page.getByLabel("Електронна пошта").fill(ADMIN_EMAIL);
  await page.getByLabel("Пароль").fill(ADMIN_PASSWORD);
  await page.getByRole("button", { name: "Увійти" }).click();
  await expect(page.getByRole("link", { name: /Родина Коваленків \(демо\)/ })).toBeVisible();

  const tag = `${testInfo.project.name}-${testInfo.repeatEachIndex}-${Date.now() % 1000000}`;
  const placeName = `Хутір ${tag}`;
  const trees = await (await page.request.get("/api/v1/trees")).json();
  const treeId = trees.find((t: { name: string }) => t.name.includes("демо")).id;
  const csrf = (await page.context().cookies()).find((c) => c.name === "korinnia_csrf")!.value;
  const created = await page.request.post(`/api/v1/trees/${treeId}/persons`, {
    data: { names: [{ first_name: "Марія", last_name: `Місце${tag}`, is_primary: true }] },
    headers: { "X-CSRF-Token": csrf },
  });
  expect(created.status()).toBe(201);
  const personId = (await created.json()).id;
  const editor = `/trees/${treeId}/people/${personId}/edit?tab=media`;

  await page.goto(editor);
  await page.getByLabel("Вибрати файли").setInputFiles({
    name: `place-${tag}.jpg`,
    mimeType: "image/jpeg",
    buffer: await makeJpeg(page, tag),
  });
  const describe = page.getByRole("dialog", { name: "Опишіть фото" });
  await describe.getByLabel("Опис").fill(`Біля хати ${tag}`);
  await describe.getByRole("combobox", { name: "Місце" }).fill(placeName);
  await page.getByRole("option", { name: `+ Створити «${placeName}»` }).click();

  // The "New place" dialog opens over the description. Its form used to sit inside the
  // description's form, so "Create" reloaded the page and the photo was lost.
  const newPlace = page.getByRole("dialog", { name: "Нове місце" });
  await expect(
    newPlace.getByTestId("map-picker").locator("img.leaflet-tile-loaded").first(),
  ).toBeVisible({ timeout: 15_000 });
  await newPlace.getByRole("button", { name: "Створити" }).click();
  await expect(newPlace).toHaveCount(0);
  await expect(page).toHaveURL((url) => url.pathname + url.search === editor);
  await expect(describe.getByText(placeName)).toBeVisible();

  await describe.getByRole("button", { name: "Зберегти" }).click();
  await expect(describe).toHaveCount(0);
  const row = page.locator("li").filter({ hasText: `place-${tag}.jpg` });
  await expect(row).toBeVisible();
  const media = await (
    await page.request.get(`/api/v1/trees/${treeId}/media?person_id=${personId}`)
  ).json();
  expect(media.items[0].place.name).toBe(placeName);
});
