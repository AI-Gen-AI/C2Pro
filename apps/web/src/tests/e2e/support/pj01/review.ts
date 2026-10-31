/**
 * PJ-01 human-in-the-loop gate: decide the pending review of a document revision through the UI.
 *
 * With the AI provider deterministic the analysis is "not assessed" and the pipeline pauses at the
 * mandatory human review (`review_required`). This harness does what an authorized person does —
 * opens the review from the document row, approves the item in the review queue and confirms the
 * dialog — and never calls the approval endpoint itself. The gate is not bypassed: the document
 * only finishes analysis because the application accepted a real human decision.
 */
import { expect, type Page, type Response } from "@playwright/test";

import { clickProjectTab } from "./health";
import type { Pj01RunRecorder } from "./run-recorder";

export interface ReviewDecision {
  itemId: string;
  /** ISO instant (zone-less UTC, as the API stores it) at which the person approved. */
  approvedAt: string;
  /** The analysis generation the approved item belongs to (revision 1 -> g1, revision 2 -> g2). */
  generation: number | null;
  status: string;
  /** Who the application recorded as the approver (an identity, not a secret). */
  approvedBy: string;
}

interface ApprovedItem {
  item_id?: string;
  current_status?: string;
  approved_at?: string | null;
  approved_by?: string | null;
  item_data?: { document_id?: string; thread_id?: string };
}

export async function approvePendingReviewThroughUi(
  page: Page,
  recorder: Pj01RunRecorder,
  options: { projectId: string; documentId: string; expectedGeneration: number; label: string },
): Promise<ReviewDecision> {
  const { projectId, documentId, expectedGeneration, label } = options;

  await clickProjectTab(page, recorder, projectId, "documents", "DOCUMENTS_TAB_NOT_NAVIGABLE");
  await page.waitForURL(new RegExp(`/projects/${projectId}/documents`), { timeout: 30_000 });
  const row = page.getByTestId(`document-row-${documentId}`);
  await expect(row).toBeVisible({ timeout: 30_000 });

  const reviewLink = row.getByTestId("document-review-cta");
  if ((await reviewLink.count()) === 0) {
    recorder.violation(
      "REVIEW_CTA_MISSING",
      `${label}: the row waits for a human decision but offers no way to open the review`,
    );
    throw new Error(`PJ01_REVIEW_CTA_MISSING: ${label}`);
  }
  await reviewLink.first().click();
  await expect(page.getByTestId("review-page")).toBeVisible({ timeout: 30_000 });

  const approve = page.locator('[data-testid^="approve-"]');
  await expect(approve.first(), `${label}: a review item with an approve action`).toBeVisible({ timeout: 60_000 });
  const pending = await approve.count();
  if (pending !== 1) {
    recorder.violation("REVIEW_QUEUE_UNEXPECTED_ITEMS", `${label}: ${pending} items await a decision, expected exactly 1`);
  }
  await expect(approve.first()).toBeEnabled({ timeout: 120_000 });
  await recorder.screenshot(page, `review-${label.replace(/\s+/g, "-")}`);

  const approved = page.waitForResponse(
    (response: Response) =>
      response.request().method() === "POST" && /\/hitl\/queue\/[^/]+\/approve/.test(new URL(response.url()).pathname),
    { timeout: 120_000 },
  );
  await approve.first().click();
  await expect(page.getByRole("dialog", { name: /approve review item/i })).toBeVisible();
  await page.getByRole("button", { name: /confirm approve/i }).click();
  const response = await approved;
  if (!response.ok()) {
    const body = (await response.text().catch(() => "")).slice(0, 300);
    throw new Error(`PJ01_REVIEW_APPROVAL_REJECTED: ${label}: HTTP ${response.status()} ${body}`);
  }

  const item = (await response.json()) as ApprovedItem;
  if (item.item_data?.document_id !== documentId) {
    recorder.violation(
      "REVIEW_ITEM_FOR_ANOTHER_DOCUMENT",
      `${label}: the approved item belongs to ${item.item_data?.document_id}, not ${documentId}`,
    );
  }
  const generation = Number(item.item_data?.thread_id?.match(/:g(\d+):/)?.[1] ?? NaN);
  if (generation !== expectedGeneration) {
    recorder.violation(
      "REVIEW_ITEM_WRONG_GENERATION",
      `${label}: the approved analysis generation is ${Number.isNaN(generation) ? "unknown" : generation}, expected ${expectedGeneration}`,
    );
  }
  if (!item.approved_at || !/^approved$/i.test(item.current_status ?? "")) {
    recorder.violation("REVIEW_NOT_RECORDED_AS_APPROVED", `${label}: approved_at=${item.approved_at} status=${item.current_status}`);
  }
  // The decision must carry an identity: an approval nobody is accountable for is not a human decision.
  if (!item.approved_by?.trim()) {
    recorder.violation("REVIEW_APPROVER_MISSING", `${label}: the approved item names no approver`);
  }
  const decision: ReviewDecision = {
    itemId: String(item.item_id ?? ""),
    approvedAt: String(item.approved_at ?? ""),
    generation: Number.isNaN(generation) ? null : generation,
    status: String(item.current_status ?? ""),
    approvedBy: String(item.approved_by ?? ""),
  };
  recorder.record(`review.${label}`, decision);
  return decision;
}

/** Leave the review page for the Documents tab, where processing resumes and is observed. */
export async function returnToDocuments(page: Page, recorder: Pj01RunRecorder, projectId: string): Promise<void> {
  await clickProjectTab(page, recorder, projectId, "documents", "DOCUMENTS_TAB_NOT_NAVIGABLE");
  await page.waitForURL(new RegExp(`/projects/${projectId}/documents`), { timeout: 30_000 });
}
