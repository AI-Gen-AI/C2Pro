/**
 * Test Suite ID: S3-03
 * Roadmap Reference: S3-03 Dynamic watermark (pseudonymized ID)
 */
import { test, expect } from "@playwright/test";

test("S3-03 RED - evidence route renders pseudonymized watermark without raw PII", async ({
  page,
}) => {
  await page.goto("/dashboard/projects/proj_demo_001/evidence");

  await expect(page.getByTestId("evidence-watermark-overlay")).toBeVisible();
  await expect(page.getByTestId("evidence-watermark-overlay")).toContainText(/USR-|ANON-/i);

  await expect(page.getByText(/jane\.doe@acme\.com/i)).toHaveCount(0);
  await expect(page.getByText(/\+1\s?\(?555\)?/i)).toHaveCount(0);
});
