/**
 * Test Suite ID: S3-06
 * Roadmap Reference: S3-06 Alert undo + double invalidation
 */
import { test, expect } from "@playwright/test";

test("S3-06 RED - approve then undo rolls back coherence metrics", async ({ page }) => {
  await page.goto("/dashboard/projects/proj_demo_001/alerts");

  await page.getByRole("button", { name: /approve/i }).first().click();
  await page.getByRole("checkbox", { name: /i confirm approval/i }).check();
  await page.getByRole("button", { name: /confirm approve/i }).click();

  await expect(page.getByText(/approved/i).first()).toBeVisible();
  await page.getByRole("button", { name: /undo/i }).click();
  await expect(page.getByText(/pending/i).first()).toBeVisible();
  await expect(page.getByTestId("coherence-freshness")).toContainText(/fresh/i);
});

test("S3-06 RED - rapid approve reject undo stays fresh after navigation", async ({ page }) => {
  await page.goto("/dashboard/projects/proj_demo_001/alerts");

  await page.getByRole("button", { name: /approve/i }).first().click();
  await page.getByRole("checkbox", { name: /i confirm approval/i }).check();
  await page.getByRole("button", { name: /confirm approve/i }).click();

  await page.getByRole("button", { name: /reject/i }).first().click();
  await page.getByLabel(/rejection reason/i).fill("False positive");
  await page.getByRole("button", { name: /confirm reject/i }).click();

  await page.getByRole("button", { name: /undo/i }).click();
  await page.reload();

  await expect(page.getByTestId("coherence-freshness")).toContainText(/fresh/i);
  await expect(page.getByTestId("alert-state-consistency")).toContainText(/consistent/i);
});
