/**
 * Test Suite ID: TS-E2E-COH-V1-09
 * Coverage: Coherence v1 null-score banner and v1 score recovery journey.
 */
import { expect, test } from "@playwright/test";
import { mkdirSync } from "node:fs";
import path from "node:path";

const screenshotDir = path.resolve(process.cwd(), "../../blackboard/coh-v1/screenshots");

test("contract-only audit shows AUDIT_INCOMPLETE then full triplet unlocks v1 score", async ({
  page,
}) => {
  mkdirSync(screenshotDir, { recursive: true });

  await page.goto("/demo/coherence-v1");

  await expect(
    page.getByText(/supply missing dimensions to unlock full coherence score/i),
  ).toBeVisible();
  await expect(page.getByText(/schedule, budget/i)).toBeVisible();
  await page.screenshot({
    fullPage: true,
    path: path.join(screenshotDir, "phase9-audit-incomplete.png"),
  });

  await page.getByRole("button", { name: /copy message audit-incomplete/i }).click();
  await expect(page.getByText(/copied/i)).toBeVisible();
  await page.screenshot({
    fullPage: true,
    path: path.join(screenshotDir, "phase9-alert-copy.png"),
  });

  await page.getByRole("button", { name: /show v0 historical row/i }).click();
  await expect(page.getByLabel(/legacy flag-based coherence score/i)).toBeVisible();
  await page.screenshot({
    fullPage: true,
    path: path.join(screenshotDir, "phase9-v0-historical.png"),
  });

  await page.getByRole("button", { name: /supply schedule and budget/i }).click();

  await expect(page.getByText(/coherence score v1 is active/i).first()).toBeVisible();
  await expect(page.getByLabel(/v1 exponential-decay coherence score/i)).toBeVisible();
  await expect(page.getByText(/82/)).toBeVisible();
  await expect(
    page.getByText(/supply missing dimensions to unlock full coherence score/i),
  ).toHaveCount(0);
  await page.screenshot({
    fullPage: true,
    path: path.join(screenshotDir, "phase9-v1-fresh.png"),
  });
  await expect(page.getByRole("region", { name: /email template preview/i })).toBeVisible();
  await page.screenshot({
    fullPage: true,
    path: path.join(screenshotDir, "phase9-email-template-preview.png"),
  });
});
