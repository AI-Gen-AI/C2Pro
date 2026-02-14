/**
 * Test Suite ID: S3-01
 * Roadmap Reference: S3-01 PDF renderer (lazy) + clause highlighting
 */
import { test, expect } from "@playwright/test";

test("S3-01 RED - project evidence highlights in PDF viewer", async ({ page }) => {
  await page.goto("/dashboard/projects/proj_demo_001/evidence");

  await expect(page.getByRole("heading", { name: /evidence viewer/i })).toBeVisible();
  await page.getByRole("button", { name: /view evidence c-101/i }).click();

  await expect(page.getByTestId("pdf-page-canvas")).toBeVisible();
  await expect(page.getByTestId("highlight-h1")).toHaveAttribute("data-active", "true");
});
