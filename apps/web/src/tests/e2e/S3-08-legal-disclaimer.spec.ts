/**
 * Test Suite ID: S3-08
 * Roadmap Reference: S3-08 Legal disclaimer modal (Gate 8)
 */
import { test, expect } from "@playwright/test";

test("S3-08 RED - first-time user must accept disclaimer before Gate 8 route", async ({ page }) => {
  await page.goto("/dashboard/projects/proj_demo_001/coherence");

  await expect(page.getByRole("dialog", { name: /legal disclaimer/i })).toBeVisible();
  await expect(page.getByTestId("legal-gate-state")).toContainText(/blocked/i);

  await page.getByRole("checkbox", { name: /i have read/i }).check();
  await page.getByRole("button", { name: /confirm acceptance/i }).click();

  await expect(page.getByRole("dialog", { name: /legal disclaimer/i })).toHaveCount(0);
});

test("S3-08 RED - accepted current version bypasses modal, version bump re-prompts", async ({ page }) => {
  await page.goto("/dashboard/projects/proj_demo_001/coherence");

  await expect(page.getByRole("dialog", { name: /legal disclaimer/i })).toHaveCount(0);

  await page.goto("/dashboard/projects/proj_demo_001/coherence?disclaimerVersion=v2.0");
  await expect(page.getByRole("dialog", { name: /legal disclaimer/i })).toBeVisible();
});
