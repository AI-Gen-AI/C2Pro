/**
 * PJ-01 revision authority: which revision does the application treat as the document's current
 * state, as a person can verify it through Health -> Evidence?
 *
 * Health cites supporting clauses. Following the BUDGET citation into the Evidence workspace
 * loads the document's entities, and every entity names the immutable revision it was read from.
 * That revision id is compared with the revision identities proven by the fixture-bound revision
 * event (blob hashes of the committed contract A and B files), so the verdict never rests on the
 * answer being judged.
 */
import { expect, type Page, type Response } from "@playwright/test";

import type { HealthVectorPayload } from "../../../pj01/health-evaluator";
import {
  evaluateHealthEvidenceRevision,
  parseInstant,
  revisionOfClause,
  type EvidenceEntityLike,
} from "../../../pj01/revision-authority-evaluator";
import { clickProjectTab, openHealthThroughNavigation } from "./health";
import type { Pj01RunRecorder } from "./run-recorder";

export interface HealthEvidenceRevision {
  clauseId: string;
  revisionId: string | null;
  entities: EvidenceEntityLike[];
  healthComputedAt: string | null;
  /** How many times the Health page had to be opened again for the post-decision snapshot. */
  attempts: number;
}

/**
 * Open Health, follow the BUDGET supporting clause into Evidence and report the revision that
 * clause belongs to. With `notBefore`, Health is re-opened (through navigation, like a person
 * coming back to the page) until it was computed at or after that instant: the analysis can be
 * shown as finished a moment before the Health snapshot that follows it lands.
 */
export async function readHealthEvidenceRevision(
  page: Page,
  recorder: Pj01RunRecorder,
  options: { projectId: string; documentId: string; notBefore?: string; waitMs?: number },
): Promise<HealthEvidenceRevision> {
  const { projectId, documentId } = options;
  const deadline = Date.now() + (options.waitMs ?? 60_000);
  let attempts = 0;
  let vector: HealthVectorPayload;

  for (;;) {
    attempts += 1;
    if (attempts > 1) {
      await clickProjectTab(page, recorder, projectId, "documents", "DOCUMENTS_TAB_NOT_NAVIGABLE");
      await page.waitForURL(new RegExp(`/projects/${projectId}/documents`), { timeout: 30_000 });
    }
    vector = await openHealthThroughNavigation(page, recorder, { projectId });
    const fresh =
      !options.notBefore || (vector.computed_at != null && parseInstant(vector.computed_at) >= parseInstant(options.notBefore));
    if (fresh || Date.now() > deadline) break;
    await page.waitForTimeout(3_000);
  }

  const tile = page.getByTestId("health-category-BUDGET");
  await expect(tile).toBeVisible({ timeout: 30_000 });
  const link = tile.getByTestId("health-evidence-link").first();
  await expect(link, "the BUDGET tile must offer a supporting clause").toBeVisible({ timeout: 30_000 });
  const clauseId = (await link.getAttribute("data-clause-id")) ?? "";

  const entitiesResponse = page.waitForResponse(
    (response: Response) =>
      response.request().method() === "GET" &&
      response.ok() &&
      new RegExp(`/documents/${documentId}/entities/?$`).test(new URL(response.url()).pathname),
    { timeout: 60_000 },
  );
  await link.click();
  await page.waitForURL(new RegExp(`/projects/${projectId}/evidence\\?`), { timeout: 30_000 });
  const entities = (await (await entitiesResponse).json()) as EvidenceEntityLike[];

  return {
    clauseId,
    revisionId: revisionOfClause(entities, clauseId),
    entities,
    healthComputedAt: vector.computed_at ?? null,
    attempts,
  };
}

export function judgeHealthEvidenceRevision(
  recorder: Pj01RunRecorder,
  read: HealthEvidenceRevision,
  expectation: { expectedRevisionId: string; otherRevisionId?: string; phase: string },
): void {
  for (const violation of evaluateHealthEvidenceRevision({ clauseId: read.clauseId, entities: read.entities }, expectation)) {
    recorder.violation(`REVISION_AUTHORITY_${violation.code}`, violation.detail);
  }
  recorder.record(`healthEvidenceRevision.${expectation.phase}`, {
    clauseId: read.clauseId,
    revisionId: read.revisionId,
    expectedRevisionId: expectation.expectedRevisionId,
    healthComputedAt: read.healthComputedAt,
    attempts: read.attempts,
  });
  if (read.attempts > 1) {
    recorder.violation(
      "ANALYZED_BEFORE_HEALTH_SNAPSHOT",
      `${expectation.phase}: the document was shown as analyzed but Health still reflected the previous state until it was opened ${read.attempts} times`,
      { blocking: false },
    );
  }
}
