import { expect, test } from "@playwright/test";

test.describe("S1-12 E2E demo access", () => {
  test("allows direct access to demo projects page", async ({ page }) => {
    await page.goto("/demo/projects", { waitUntil: "domcontentloaded" });

    await expect(page.getByRole("heading", { name: "Projects" })).toBeVisible();
    await expect(page.getByRole("status", { name: /demo mode banner/i })).toBeVisible();
  });

  test("navigates from landing to live demo", async ({ page }) => {
    await page.goto("/", { waitUntil: "domcontentloaded" });
    await page.getByRole("link", { name: "View Live Demo" }).click();

    await expect(page).toHaveURL(/\/demo\/projects$/);
    await expect(page.getByRole("heading", { name: "Projects" })).toBeVisible();
  });
});
