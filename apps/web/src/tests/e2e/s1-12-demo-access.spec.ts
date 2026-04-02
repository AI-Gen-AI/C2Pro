import { expect, test } from "@playwright/test";

test.describe("S1-12 E2E demo access", () => {
  test("allows direct access to demo documents page", async ({ page }) => {
    await page.goto("/demo/documents", { waitUntil: "domcontentloaded" });

    await expect(page.getByRole("heading", { name: "Documents" })).toBeVisible({
      timeout: 20_000,
    });
  });

  test("navigates from landing to live demo", async ({ page }) => {
    await page.goto("/", { waitUntil: "domcontentloaded" });
    await page.getByRole("link", { name: "View Live Demo" }).click();

    await expect(page.getByRole("heading", { name: "Documents" })).toBeVisible({
      timeout: 20_000,
    });
  });
});
