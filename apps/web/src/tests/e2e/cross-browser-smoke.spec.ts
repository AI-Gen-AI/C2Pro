/**
 * Backlog Task: TASK-024
 * Scope: Cross-browser smoke coverage for public entry flow
 */
import { expect, test } from "@playwright/test";

test.describe("TASK-024 cross-browser smoke", () => {
  test("loads the landing page and opens the public live demo entry point", async ({
    page,
  }) => {
    await page.goto("/", { waitUntil: "domcontentloaded" });

    await expect(
      page.getByRole("link", { name: /view live demo/i }),
    ).toBeVisible({ timeout: 20_000 });

    await page.getByRole("link", { name: /view live demo/i }).click();

    await expect(
      page.getByRole("heading", { name: /^documents$/i }),
    ).toBeVisible({ timeout: 20_000 });
  });
});
