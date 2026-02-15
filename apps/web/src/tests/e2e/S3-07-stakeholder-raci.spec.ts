/**
 * Test Suite ID: S3-07
 * Roadmap Reference: S3-07 Severity badge + Stakeholder Map + RACI
 */
import { test, expect } from "@playwright/test";

test("S3-07 RED - stakeholder scatter + raci + severity-linked alerts", async ({ page }) => {
  await page.goto("/dashboard/projects/proj_demo_001/stakeholders");

  await expect(page.getByRole("heading", { name: /stakeholder map/i })).toBeVisible();
  await page.getByTestId("stakeholder-node-s1").click();
  await expect(page.getByTestId("raci-grid")).toBeVisible();

  await page.getByTestId("raci-cell-w1-s1").click();
  await page.getByRole("button", { name: /set accountable/i }).click();
  await page.getByRole("button", { name: /save raci/i }).click();

  await expect(page.getByTestId("severity-badge-critical")).toBeVisible();
});

test("S3-07 RED - keyboard traversal across badges, scatter nodes and raci cells", async ({ page }) => {
  await page.goto("/dashboard/projects/proj_demo_001/stakeholders");

  await page.keyboard.press("Tab");
  await page.keyboard.press("Tab");
  await page.keyboard.press("Enter");

  await expect(page.getByTestId("stakeholder-node-s1")).toHaveAttribute("data-highlighted", "true");

  await page.keyboard.press("Tab");
  await page.keyboard.press("Enter");
  await expect(page.getByRole("button", { name: /save raci/i })).toBeVisible();
});
