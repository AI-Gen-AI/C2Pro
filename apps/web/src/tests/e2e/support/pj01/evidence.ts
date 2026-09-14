/**
 * PJ-01 step 7: navigate toward Evidence for the uploaded document.
 *
 * Clickable Health → Evidence traceability is owned by another lane; this harness only
 * RECORDS whether the Health view links to Evidence (gap G5, non-blocking here) and reaches
 * the Evidence workspace for the uploaded document through visible project navigation.
 */
import { expect, type Page } from "@playwright/test";

import { clickProjectTab } from "./health";
import type { Pj01RunRecorder } from "./run-recorder";

export async function navigateTowardEvidence(
  page: Page,
  recorder: Pj01RunRecorder,
  options: { projectId: string; documentId: string },
): Promise<void> {
  const { projectId, documentId } = options;

  const healthRegion = page.getByRole("region", { name: "Document health" });
  const evidenceLinks = healthRegion.locator(`a[href*="/projects/${projectId}/evidence"]`);
  const linkedFromHealth = (await healthRegion.count()) > 0 && (await evidenceLinks.count()) > 0;
  recorder.record("healthLinksToEvidence", linkedFromHealth);
  if (!linkedFromHealth) {
    recorder.gap(
      "G5_HEALTH_TO_EVIDENCE_NOT_LINKED",
      "Health evidence is not clickable into the Evidence viewer (owned by the Health → Evidence traceability lane)",
      { blocking: false },
    );
  }

  await clickProjectTab(page, recorder, projectId, "evidence", "EVIDENCE_TAB_NOT_NAVIGABLE");
  await page.waitForURL(new RegExp(`/projects/${projectId}/evidence`), { timeout: 30_000 });

  // Open the uploaded document's evidence from its Documents row link (visible navigation).
  await clickProjectTab(page, recorder, projectId, "documents", "DOCUMENTS_TAB_NOT_NAVIGABLE");
  await page.waitForURL(new RegExp(`/projects/${projectId}/documents`), { timeout: 30_000 });
  const row = page.getByTestId(`document-row-${documentId}`);
  await expect(row).toBeVisible({ timeout: 30_000 });
  await row.getByRole("link").first().click();
  await page.waitForURL(new RegExp(`/projects/${projectId}/evidence\\?documentId=${documentId}`), { timeout: 30_000 });
  await expect(page.getByText(/could not load|failed to load/i)).toHaveCount(0);
  recorder.record("evidenceReachedBy", "documents-row-link");
}
