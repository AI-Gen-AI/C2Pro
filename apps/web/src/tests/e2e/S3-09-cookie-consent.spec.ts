/**
 * Test Suite ID: S3-09
 * Roadmap Reference: S3-09 Cookie consent banner (GDPR)
 */
import { test, expect } from "@playwright/test";

test("S3-09 RED - first-time user configures preferences and tracker gating follows", async ({ page }) => {
  await page.goto("/dashboard");

  await expect(page.getByRole("region", { name: /cookie consent/i })).toBeVisible();
  await page.getByRole("button", { name: /manage preferences/i }).click();
  await page.getByRole("checkbox", { name: /analytics cookies/i }).check();
  await page.getByRole("button", { name: /save preferences/i }).click();

  await expect(page.getByTestId("tracker-analytics-state")).toContainText(/enabled/i);
  await expect(page.getByTestId("tracker-marketing-state")).toContainText(/blocked/i);
});

test("S3-09 RED - version bump re-prompts returning user", async ({ page }) => {
  await page.goto("/dashboard?cookiePolicyVersion=2026-02");
  await expect(page.getByRole("region", { name: /cookie consent/i })).toHaveCount(0);

  await page.goto("/dashboard?cookiePolicyVersion=2026-03");
  await expect(page.getByRole("region", { name: /cookie consent/i })).toBeVisible();
});
