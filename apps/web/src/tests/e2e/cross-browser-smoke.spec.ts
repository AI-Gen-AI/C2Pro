/**
 * Backlog Task: TASK-024
 * Scope: Cross-browser smoke coverage for public entry flow
 */
import { expect, test } from "@playwright/test";

test.describe("TASK-024 cross-browser smoke", () => {
  test("loads the landing page and opens the live demo entry point", async ({
    page,
  }) => {
    await page.goto("/", { waitUntil: "domcontentloaded" });

    await expect(
      page.getByRole("link", { name: /view live demo/i }),
    ).toBeVisible();

    await page.getByRole("link", { name: /view live demo/i }).click();

    await expect(page).toHaveURL(/\/projects$/);
    await expect(
      page.getByRole("heading", { name: /^projects$/i }),
    ).toBeVisible();
  });
});
