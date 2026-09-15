/**
 * PJ-01 step 7: follow Health → Evidence for the uploaded document.
 *
 * The Health view names its source document (`single_document_coverage.document_id`) and links
 * each supporting clause to `/projects/{id}/evidence?documentId=…&highlightId=…`. This harness
 * clicks that visible link — never a typed URL — and judges the landing: the Evidence workspace
 * must open exactly the source document with exactly that clause active. A missing link, a
 * document-granular assessment, or a wrong landing is recorded, never weakened into a pass.
 */
import { expect, type Page } from "@playwright/test";

import { evaluateEvidenceLanding, type HealthVectorPayload } from "../../../pj01/health-evaluator";
import { clickProjectTab } from "./health";
import type { Pj01RunRecorder } from "./run-recorder";

export async function navigateTowardEvidence(
  page: Page,
  recorder: Pj01RunRecorder,
  options: { projectId: string; documentId: string; health: HealthVectorPayload },
): Promise<void> {
  const { projectId, documentId, health } = options;

  const healthRegion = page.getByRole("region", { name: "Document health" });
  const clauseLinks = healthRegion.getByTestId("health-evidence-link");
  const clauseLinkCount = (await healthRegion.count()) > 0 ? await clauseLinks.count() : 0;
  recorder.record("healthEvidenceClauseLinks", clauseLinkCount);
  recorder.record("healthEvidenceGranularity", health.single_document_evidence_granularity ?? null);

  if (clauseLinkCount === 0) {
    recorder.record("healthToEvidence", "NO_CLAUSE_LINK");
    recorder.gap(
      "G5_HEALTH_TO_EVIDENCE_NOT_LINKED",
      "Health shows no clickable supporting clause for the uploaded document (no clause-granular evidence, or no attributed source document)",
      { blocking: false },
    );
    await reachEvidenceFromDocumentsRow(page, recorder, { projectId, documentId });
    return;
  }

  const link = clauseLinks.first();
  const clauseId = await link.getAttribute("data-clause-id");
  if (!clauseId) {
    recorder.violation("HEALTH_EVIDENCE_LINK_WITHOUT_CLAUSE", "health-evidence-link carries no data-clause-id");
    return;
  }
  await link.click();
  await page.waitForURL(new RegExp(`/projects/${projectId}/evidence\\?`), { timeout: 30_000 });

  const activeCard = page.locator('[data-testid="evidence-entity-card"][data-active="true"]');
  const unavailable = page.getByTestId("evidence-link-unavailable");
  await expect(activeCard.or(unavailable).first()).toBeVisible({ timeout: 30_000 });

  const violations = evaluateEvidenceLanding(
    {
      url: page.url(),
      activeEntityId: (await activeCard.count()) === 1 ? await activeCard.getAttribute("data-entity-id") : null,
      unavailableNotice: (await unavailable.count()) > 0 ? await unavailable.innerText() : null,
    },
    { documentId, clauseId },
  );
  for (const violation of violations) {
    recorder.violation(`HEALTH_TO_${violation.code}`, violation.detail);
  }
  recorder.record("healthToEvidence", violations.length === 0 ? "EXACT_DOCUMENT_AND_CLAUSE" : "WRONG_LANDING");
  recorder.record("evidenceReachedBy", "health-supporting-clause-link");
  await expect(page.getByText(/could not load|failed to load/i)).toHaveCount(0);
}

async function reachEvidenceFromDocumentsRow(
  page: Page,
  recorder: Pj01RunRecorder,
  options: { projectId: string; documentId: string },
): Promise<void> {
  const { projectId, documentId } = options;
  await clickProjectTab(page, recorder, projectId, "documents", "DOCUMENTS_TAB_NOT_NAVIGABLE");
  await page.waitForURL(new RegExp(`/projects/${projectId}/documents`), { timeout: 30_000 });
  const row = page.getByTestId(`document-row-${documentId}`);
  await expect(row).toBeVisible({ timeout: 30_000 });
  await row.getByRole("link").first().click();
  await page.waitForURL(new RegExp(`/projects/${projectId}/evidence\\?documentId=${documentId}`), { timeout: 30_000 });
  await expect(page.getByText(/could not load|failed to load/i)).toHaveCount(0);
  recorder.record("evidenceReachedBy", "documents-row-link");
}
