/**
 * Test Suite ID: S3-05
 * Roadmap Reference: S3-05 Focus-scoped keyboard shortcuts (WCAG 2.1.4)
 */
import { test, expect } from "@playwright/test";

test("S3-05 RED - keyboard flow across evidence and alerts avoids accidental typing activation", async ({
  page,
}) => {
  await page.goto("/dashboard/projects/proj_demo_001/evidence");

  await page.keyboard.press("KeyJ");
  await expect(page.getByTestId("shortcut-evidence-cursor")).toContainText("1");

  await page.getByLabel(/notes/i).click();
  await page.keyboard.press("KeyJ");
  await expect(page.getByTestId("shortcut-evidence-cursor")).toContainText("1");

  await page.goto("/dashboard/projects/proj_demo_001/alerts");
  await page.keyboard.press("KeyA");
  await expect(page.getByTestId("shortcut-alert-status")).toContainText(/approved/i);
});

test("S3-05 RED - WCAG 2.1.4 disable path keeps equivalent actions accessible", async ({ page }) => {
  await page.goto("/dashboard/projects/proj_demo_001/alerts");

  await page.getByRole("button", { name: /keyboard settings/i }).click();
  await page.getByRole("switch", { name: /disable single-character shortcuts/i }).click();

  await page.keyboard.press("KeyA");
  await expect(page.getByTestId("shortcut-alert-status")).toContainText(/pending/i);

  await page.getByRole("button", { name: /approve selected alert/i }).click();
  await expect(page.getByTestId("shortcut-alert-status")).toContainText(/approved/i);
});
