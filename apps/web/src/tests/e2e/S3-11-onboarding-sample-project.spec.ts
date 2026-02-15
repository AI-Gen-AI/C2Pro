/**
 * Test Suite ID: S3-11
 * Roadmap Reference: S3-11 Onboarding sample project frontend
 */
import { test, expect } from "@playwright/test";

test("S3-11 RED - new user reaches sample project workspace quickly", async ({ page }) => {
  await page.goto("/dashboard");

  await page.getByRole("button", { name: /start with sample project/i }).click();
  await expect(page).toHaveURL(/\/dashboard\/projects\/proj_sample_001/i);
  await expect(page.getByText(/time-to-value/i)).toBeVisible();
});

test("S3-11 RED - retry after transient provisioning error recovers to ready", async ({ page }) => {
  await page.goto("/dashboard?onboardingFail=1");

  await expect(page.getByRole("alert")).toHaveTextContent(/provisioning timed out/i);
  await page.getByRole("button", { name: /retry setup/i }).click();

  await expect(page).toHaveURL(/\/dashboard\/projects\/proj_sample_001/i);
});
