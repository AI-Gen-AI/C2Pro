/**
 * Test Suite ID: S3-12
 * Roadmap Reference: S3-12 A11y audit pass 1 + responsive pass (tablet)
 */
import { test, expect } from "@playwright/test";

test("S3-12 RED - axe critical and keyboard blockers are zero on key routes", async ({ page }) => {
  await page.goto("/dashboard");

  await expect(page.getByTestId("a11y-critical-count")).toContainText("0");
  await expect(page.getByTestId("keyboard-blocker-count")).toContainText("0");
});

test("S3-12 RED - tablet portrait/landscape sanity across alerts/evidence/onboarding", async ({ page }) => {
  await page.setViewportSize({ width: 768, height: 1024 });
  await page.goto("/dashboard/projects/proj_demo_001/alerts");
  await expect(page.getByRole("heading", { name: /alert review center/i })).toBeVisible();

  await page.setViewportSize({ width: 1180, height: 820 });
  await page.goto("/dashboard/projects/proj_demo_001/evidence");
  await expect(page.getByRole("heading", { name: /evidence viewer/i })).toBeVisible();
});
