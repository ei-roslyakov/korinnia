import { expect, test, type Page } from "@playwright/test";

const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL ?? "admin@example.com";
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? "change-me-now-please";

/** A real JPEG drawn in the browser (no binary fixtures in the repo). */
async function makeJpeg(page: Page, label: string): Promise<Buffer> {
  const b64 = await page.evaluate((text) => {
    const c = document.createElement("canvas");
    c.width = 640;
    c.height = 480;
    const g = c.getContext("2d")!;
    g.fillStyle = "#c8a46e";
    g.fillRect(0, 0, 640, 480);
    g.fillStyle = "#3f6212";
    g.beginPath();
    g.arc(320, 200, 90, 0, Math.PI * 2);
    g.fill();
    g.fillStyle = "#000";
    g.font = "32px sans-serif";
    g.fillText(text, 40, 440);
    return c.toDataURL("image/jpeg", 0.9).split(",")[1]!;
  }, label);
  return Buffer.from(b64, "base64");
}

test("upload a photo, previews are generated, it becomes the portrait", async ({
  page,
}, testInfo) => {
  await page.goto("/login");
  await page.getByLabel("Електронна пошта").fill(ADMIN_EMAIL);
  await page.getByLabel("Пароль").fill(ADMIN_PASSWORD);
  await page.getByRole("button", { name: "Увійти" }).click();
  await page.getByRole("link", { name: /Родина Коваленків \(демо\)/ }).click();

  // Unique per run and repeat, so parallel copies of this test never see each other's rows.
  const tag = `${testInfo.project.name}-${testInfo.repeatEachIndex}-${Date.now() % 100000}`;
  // Each run gets its own person: parallel runs would otherwise race to set one portrait.
  const surname = `Портрет${testInfo.repeatEachIndex}${testInfo.project.name.length}${Date.now() % 1000000}`;
  const trees = await (await page.request.get("/api/v1/trees")).json();
  const treeId = trees.find((t: { name: string }) => t.name.includes("демо")).id;
  const csrf = (await page.context().cookies()).find((c) => c.name === "korinnia_csrf")!.value;
  const created = await page.request.post(`/api/v1/trees/${treeId}/persons`, {
    data: { names: [{ first_name: "Emily", last_name: surname, is_primary: true }] },
    headers: { "X-CSRF-Token": csrf },
  });
  expect(created.status()).toBe(201);

  // Open the editor (search → panel → edit).
  await page.getByRole("button", { name: "Редагування" }).click();
  await page.getByRole("combobox", { name: /Знайти людину/ }).fill(surname);
  await page.getByRole("option", { name: `Emily ${surname}` }).click();
  await page.getByRole("complementary").getByRole("link", { name: "Редагувати" }).click();
  await page.getByRole("tab", { name: "Медіа" }).click();

  const jpeg = await makeJpeg(page, tag);
  await page.getByLabel("Вибрати файли").setInputFiles({
    name: `Emily ${tag}.jpg`,
    mimeType: "image/jpeg",
    buffer: jpeg,
  });

  // Uploaded → processed by the worker → thumbnail served through nginx.
  const row = page.locator("li").filter({ hasText: `Emily ${tag}.jpg` });
  await expect(row).toBeVisible();
  await expect(row.getByText("Готую перегляд…")).toHaveCount(0, { timeout: 30_000 });
  const thumb = row.locator("img");
  await expect(thumb).toBeVisible();
  const thumbResp = await page.request.get((await thumb.getAttribute("src"))!);
  expect(thumbResp.status()).toBe(200);
  expect(thumbResp.headers()["content-type"]).toBe("image/webp");

  // The original is byte-for-byte what was uploaded.
  const media = await (
    await page.request.get(
      `/api/v1/trees/${page.url().split("/trees/")[1]!.split("/")[0]}/media?q=Emily`,
    )
  ).json();
  const item = media.items.find((m: { original_filename: string }) =>
    m.original_filename.includes(tag),
  );
  const original = await page.request.get(item.urls.original);
  expect(Buffer.from(await original.body()).equals(jpeg)).toBe(true);

  // Crop a portrait (draw a square), save.
  await row.getByRole("button", { name: "Зробити портретом" }).click();
  const dialog = page.getByRole("dialog");
  const area = dialog.getByRole("application");
  await area.locator("img").scrollIntoViewIfNeeded();
  const box = (await area.boundingBox())!;
  await page.mouse.move(box.x + box.width * 0.35, box.y + box.height * 0.2);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width * 0.65, box.y + box.height * 0.6, { steps: 5 });
  await page.mouse.up();
  await expect(dialog.getByTestId("region")).toBeVisible();
  await dialog.getByRole("button", { name: "Зберегти" }).click();
  await expect(row.getByText("Портрет", { exact: true }).first()).toBeVisible();

  // The portrait shows on the person page and opens in the lightbox.
  await page.getByRole("link", { name: "Переглянути сторінку" }).click();
  const avatar = page.locator("article header img");
  await expect(avatar).toHaveAttribute("src", /\/avatar\?v=/, { timeout: 30_000 });
  await page.getByRole("button", { name: `Emily ${tag}` }).click();
  await expect(page.getByRole("dialog").locator("img").first()).toBeVisible();
  await page.keyboard.press("Escape");
});
