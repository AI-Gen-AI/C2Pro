/**
 * TS-E2E-S5-001 — ACC-01 S5: a human can REJECT a pending review, and only with a reason.
 *
 * Replaces the conditional skips of DAP "HITL-002/HITL-003" (they targeted the unseeded demo project
 * `proj_demo_001` and never ran). Everything here is real: live Clerk sign-in, a new project created
 * through the wizard, the real .docx contract uploaded through the dialog, the real Celery worker, the
 * real HITL queue and the real reject route. The AI is mocked (C2PRO_AI_MOCK=1), so the review is
 * mandatory; it is never skipped.
 *
 * What it proves in the browser: the Reject dialog cannot be confirmed without a reason (empty and
 * whitespace-only), a real reason is accepted, the review ends REJECTED, the document does not become
 * "Analyzed", and the outcome survives a reload. The API refusing a missing/blank reason (HTTP 422, on
 * both routes that can reject) and the other negatives are proven against PostgreSQL in
 * `test_s5_hitl_reject_and_differentiated_approval.py`.
 */
import path from "node:path";

import { expect, test } from "@playwright/test";

import { Pj01RunRecorder } from "./support/pj01/run-recorder";
import { observeProcessingWithoutReload } from "./support/pj01/processing";
import { returnToDocuments } from "./support/pj01/review";
import { createProjectThroughUi, signInAsJourneyUser } from "./support/pj01/session";
import { uploadDocumentThroughUi } from "./support/pj01/upload";

const CONTRACT = path.join(process.cwd(), "src", "tests", "e2e", "test-data", "triplet", "triplet-contract.docx");
const REASON = "The extraction missed the completion-date penalty clause; re-analyse after correction.";

test.describe("TS-E2E-S5-001: HITL rejection requires a reason", () => {
  test("a rejection needs a reason and leaves the document unapproved", async ({ browser, baseURL }) => {
    test.setTimeout(600_000);
    const base = baseURL ?? "http://localhost:3100";
    const recorder = Pj01RunRecorder.fromEnv();
    // The login is live: an empty session, never the restored one.
    const context = await browser.newContext({ baseURL: base, storageState: { cookies: [], origins: [] } });
    const page = await context.newPage();

    const observation = await signInAsJourneyUser(page, base);
    const projectId = await createProjectThroughUi(page, observation, `S5 reject ${Date.now().toString(36)}`);
    const { documentId } = await uploadDocumentThroughUi(page, recorder, {
      projectId,
      filePath: CONTRACT,
      documentType: "contract",
    });

    const gate = await observeProcessingWithoutReload(page, recorder, {
      projectId,
      documentId,
      settlement: "review_required",
      label: "reject.until-review-gate",
    });
    expect(gate.evaluation.outcome, "the mandatory review must be reached, not skipped").toBe("review_required");

    // Open the review from the document row, exactly as a person does.
    const row = page.getByTestId(`document-row-${documentId}`);
    await row.getByTestId("document-review-cta").first().click();
    await expect(page.getByTestId("review-page")).toBeVisible({ timeout: 30_000 });
    const rejectAction = page.locator('[data-testid^="reject-"]').first();
    await expect(rejectAction).toBeVisible({ timeout: 60_000 });
    await expect(rejectAction).toBeEnabled({ timeout: 120_000 });
    await rejectAction.click();

    const dialog = page.getByRole("dialog", { name: /reject review item/i });
    await expect(dialog).toBeVisible();
    const confirm = dialog.getByRole("button", { name: /confirm reject/i });
    const reason = dialog.getByLabel(/rejection reason/i);

    // 1. No reason: it cannot be confirmed.
    await expect(confirm, "empty reason").toBeDisabled();
    // 2. Whitespace is not a reason either.
    await reason.fill("   \n  ");
    await expect(confirm, "whitespace-only reason").toBeDisabled();
    // 3. A real reason enables the decision and the API accepts it.
    await reason.fill(REASON);
    await expect(confirm).toBeEnabled();
    const rejected = page.waitForResponse(
      (response) =>
        response.request().method() === "POST" && /\/hitl\/queue\/[^/]+\/reject/.test(new URL(response.url()).pathname),
      { timeout: 120_000 },
    );
    await confirm.click();
    const response = await rejected;
    expect(response.status(), await response.text().catch(() => "")).toBeLessThan(300);
    const decided = (await response.json()) as { current_status?: string; approved_by?: string | null };
    expect(decided.current_status).toBe("REJECTED");
    expect(decided.approved_by, "the decision names who took it").toBeTruthy();

    await expect(page.getByTestId("stat-rejected")).toContainText("1", { timeout: 30_000 });
    await expect(page.getByTestId("stat-approved")).toContainText("0");

    // The document is not approved: it is neither "Analyzed" nor still waiting for the same review.
    await returnToDocuments(page, recorder, projectId);
    const badge = page.getByTestId(`document-row-${documentId}`).getByTestId("document-status-badge");
    await expect(badge).not.toHaveText(/analy[sz]ed/i, { timeout: 60_000 });
    await expect(badge).not.toHaveText(/review required/i, { timeout: 60_000 });
    const label = (await badge.innerText()).trim();
    test.info().annotations.push({ type: "document-state-after-rejection", description: label });

    // And it survives a reload (the decision is durable, not a client-side state).
    await page.reload();
    await expect(page.getByTestId(`document-row-${documentId}`).getByTestId("document-status-badge")).toHaveText(label, {
      timeout: 60_000,
    });
    await context.close();
  });
});
