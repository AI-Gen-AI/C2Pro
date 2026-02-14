/**
 * Test Suite ID: S3-02
 * Roadmap Reference: S3-02 Mobile Evidence Viewer (tab interface)
 */
import { test, expect } from "@playwright/test";

test("S3-02 RED addendum - mobile reload preserves deep evidence state", async ({
  page,
}) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/dashboard/projects/proj_demo_001/evidence");

  await page.getByRole("tab", { name: /alerts/i }).click();
  await page.getByRole("button", { name: /delay penalty alert/i }).click();
  await page.reload();

  await expect(page.getByRole("tab", { name: /alerts/i })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await page.getByRole("tab", { name: /pdf/i }).click();
  await expect(page.getByTestId("mobile-active-highlight")).toContainText("c-101");
});
