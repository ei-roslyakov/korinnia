import { expect, test } from "@playwright/test";

test("home page loads and backend is healthy", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Коріння");
  await expect(page.getByText("Працює")).toHaveCount(3);
});

test("security headers are set by nginx", async ({ request }) => {
  const resp = await request.get("/");
  expect(resp.headers()["x-content-type-options"]).toBe("nosniff");
  expect(resp.headers()["content-security-policy"]).toContain("default-src 'self'");
});
