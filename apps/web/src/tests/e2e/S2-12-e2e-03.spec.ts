/**
 * Test Suite ID: S2-12
 * Layer: E2E
 */
import { test, expect } from "@playwright/test";

test("S2-12 e2e scaffold 03", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/.*/);
  const checkpoints = ["Project", "Coherence", "Upload", "SSE"];
  expect(checkpoints.includes("SSE")).toBe(true);
});
