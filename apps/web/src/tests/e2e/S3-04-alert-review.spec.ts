/**
 * Test Suite ID: S3-04
 * Roadmap Reference: S3-04 Alert Review Center + approve/reject modal
 */
import { test, expect } from "@playwright/test";

test("S3-04 RED - full CRUD review journey on alerts route", async ({ page }) => {
  await page.goto("/dashboard/projects/proj_demo_001/alerts");

  await expect(page.getByRole("heading", { name: /alert review center/i })).toBeVisible();

  await page.getByRole("button", { name: /new alert/i }).click();
  await page.getByLabel(/title/i).fill("Insurance mismatch in section 4.2");
  await page.getByLabel(/severity/i).selectOption("high");
  await page.getByRole("button", { name: /create alert/i }).click();

  await expect(page.getByRole("row", { name: /insurance mismatch in section 4.2/i })).toBeVisible();

  await page.getByRole("button", { name: /edit/i }).first().click();
  await page.getByLabel(/title/i).fill("Insurance mismatch in section 4.2 updated");
  await page.getByRole("button", { name: /save changes/i }).click();

  await page.getByRole("button", { name: /approve/i }).first().click();
  await page.getByRole("checkbox", { name: /i confirm approval/i }).check();
  await page.getByRole("button", { name: /confirm approve/i }).click();
  await expect(page.getByText(/approved/i).first()).toBeVisible();

  await page.getByRole("button", { name: /reject/i }).nth(1).click();
  await page.getByLabel(/rejection reason/i).fill("Insufficient evidence");
  await page.getByRole("button", { name: /confirm reject/i }).click();
  await expect(page.getByText(/rejected/i).first()).toBeVisible();

  await page.getByRole("button", { name: /delete/i }).first().click();
  await page.getByRole("button", { name: /confirm delete/i }).click();
  await expect(page.getByText(/insurance mismatch in section 4.2 updated/i)).toHaveCount(0);
});

test("S3-04 RED - keyboard-only modal workflow retains focus and no trap regression", async ({
  page,
}) => {
  await page.goto("/dashboard/projects/proj_demo_001/alerts");

  await page.keyboard.press("Tab");
  await page.keyboard.press("Tab");
  await page.keyboard.press("Enter");

  await expect(page.getByRole("dialog")).toBeVisible();

  await page.keyboard.press("Tab");
  await page.keyboard.press("Tab");
  await page.keyboard.press("Escape");

  await expect(page.getByRole("dialog")).toHaveCount(0);
});
