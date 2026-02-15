/**
 * Test Suite ID: S3-10
 * Roadmap Reference: S3-10 sessionStorage filter persistence
 */
import { test, expect } from "@playwright/test";

test("S3-10 RED - filter chips/results persist after refresh", async ({ page }) => {
  await page.goto("/dashboard/projects/proj_demo_001/alerts");

  await page.getByRole("button", { name: /severity critical/i }).click();
  await page.getByRole("button", { name: /owner legal/i }).click();
  await page.reload();

  await expect(page.getByTestId("filter-chip-severity-critical")).toBeVisible();
  await expect(page.getByTestId("filter-chip-owner-legal")).toBeVisible();
});

test("S3-10 RED - reset clears persisted filters after refresh", async ({ page }) => {
  await page.goto("/dashboard/projects/proj_demo_001/alerts");

  await page.getByRole("button", { name: /severity critical/i }).click();
  await page.getByRole("button", { name: /reset filters/i }).click();
  await page.reload();

  await expect(page.getByTestId("filter-default-state")).toBeVisible();
});
