/**
 * TS-E2E-S3-001 — ACC-01 S3: a contract that awaits approval is a stated, honest state.
 *
 * Everything here is real except the AI provider (C2PRO_AI_MOCK=1, so the review is mandatory): live Clerk
 * sign-in, projects created through the wizard, the real .docx contract uploaded through the dialog, the real
 * Celery worker and the real `/coherence/evaluate` route. What it proves in the browser:
 *
 *  1. A project WITHOUT documents: the checklist says the contract is missing (no "awaiting approval"), and
 *     evaluating answers 404 "No document clauses found" -- nothing was uploaded.
 *  2. A project whose only contract waits for its mandatory review: the page says in words that the contract
 *     awaits approval and that nothing is evaluated; no Evaluate button is offered; evaluating anyway (the
 *     authenticated session of this browser) answers 200 with a NULL score, no alerts and
 *     `score_reason = contract_pending_approval` -- not a 404 and not a number; nothing is written (no alert
 *     rows, the Coherence page shows no score).
 *
 * The two projects are told apart by what the user sees AND by what the API answers.
 */
import path from "node:path";

import { expect, test, type Page } from "@playwright/test";

import { Pj01RunRecorder } from "./support/pj01/run-recorder";
import { observeProcessingWithoutReload } from "./support/pj01/processing";
import { createProjectThroughUi, signInAsJourneyUser } from "./support/pj01/session";
import { uploadDocumentThroughUi } from "./support/pj01/upload";

const CONTRACT = path.join(process.cwd(), "src", "tests", "e2e", "test-data", "triplet", "triplet-contract.docx");

interface ApiAnswer {
  status: number;
  body: unknown;
}

/** Calls the API with this browser's own Clerk session (the token never leaves the page callback). */
async function callApi(page: Page, method: "GET" | "POST", url: string, payload?: unknown): Promise<ApiAnswer> {
  return page.evaluate(
    async ({ method: m, url: u, payload: p }) => {
      const token = await window.Clerk?.session?.getToken();
      if (!token) throw new Error("S3_AUTH_CONTEXT_MISSING");
      const response = await fetch(u, {
        method: m,
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: p === undefined ? undefined : JSON.stringify(p),
      });
      const text = await response.text();
      let body: unknown = text;
      try {
        body = JSON.parse(text);
      } catch {
        /* keep the text */
      }
      return { status: response.status, body };
    },
    { method, url, payload },
  );
}

function alertCount(body: unknown): number {
  if (Array.isArray(body)) return body.length;
  const record = body as { items?: unknown[]; alerts?: unknown[] } | null;
  return (record?.items ?? record?.alerts ?? []).length;
}

test.describe("TS-E2E-S3-001: a contract awaiting approval is stated, not a 404 and not a score", () => {
  test("pending contract vs a project with no documents", async ({ browser, baseURL }) => {
    test.setTimeout(600_000);
    const base = baseURL ?? "http://localhost:3100";
    const recorder = new Pj01RunRecorder({ runId: `s3-pending-${new Date().toISOString().replace(/[:.]/g, "-")}` });
    // Live login: an empty session, never a restored one.
    const context = await browser.newContext({ baseURL: base, storageState: { cookies: [], origins: [] } });
    const page = await context.newPage();
    const tag = Date.now().toString(36);

    const observation = await signInAsJourneyUser(page, base);

    // ── 1. no documents ────────────────────────────────────────────────────────────────────────────────
    const emptyProjectId = await createProjectThroughUi(page, observation, `S3 empty ${tag}`);
    await expect(page.getByTestId("documents-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("triplet-awaiting-approval"), "nothing awaits approval here").toHaveCount(0);
    await expect(page.getByText("Missing").first()).toBeVisible();
    const empty = await callApi(page, "POST", "/api/v1/coherence/evaluate", { project_id: emptyProjectId });
    expect(empty.status, JSON.stringify(empty.body)).toBe(404);
    expect(JSON.stringify(empty.body)).toMatch(/No document clauses found/i);

    // ── 2. a contract that waits for its mandatory review ───────────────────────────────────────────────
    await page.goto("/projects");
    const projectId = await createProjectThroughUi(page, observation, `S3 pending ${tag}`);
    const { documentId } = await uploadDocumentThroughUi(page, recorder, {
      projectId,
      filePath: CONTRACT,
      documentType: "contract",
    });
    const gate = await observeProcessingWithoutReload(page, recorder, {
      projectId,
      documentId,
      settlement: "review_required",
      label: "s3-pending.until-review-gate",
    });
    expect(gate.evaluation.outcome, "the mandatory review must be reached, not skipped").toBe("review_required");

    // The user is told, in words, that the contract awaits approval -- and nothing is evaluated.
    const notice = page.getByTestId("triplet-awaiting-approval");
    await expect(notice).toBeVisible({ timeout: 60_000 });
    await expect(notice).toContainText(/contract is awaiting approval/i);
    await expect(notice).toContainText(/nothing is evaluated and no score is produced/i);
    await expect(page.getByText("Awaiting approval").first()).toBeVisible();
    await expect(
      page.getByRole("button", { name: /evaluate coherence/i }),
      "no evaluation is offered while the contract awaits approval",
    ).toHaveCount(0);

    // Evaluating anyway (this browser's authenticated session) answers an explicit state.
    const pending = await callApi(page, "POST", "/api/v1/coherence/evaluate", { project_id: projectId });
    expect(pending.status, JSON.stringify(pending.body)).toBe(200);
    const result = pending.body as {
      overall_score: number | null;
      alerts: unknown[];
      score_reason: string | null;
      score_missing_dimensions: string[] | null;
    };
    expect(result.overall_score, "no score is invented").toBeNull();
    expect(result.alerts, "no alert is invented").toEqual([]);
    expect(result.score_reason).toBe("contract_pending_approval");
    expect(result.score_missing_dimensions?.length ?? 0).toBeGreaterThan(0);

    // Nothing was written: no alert rows, and the Coherence page shows no score.
    const alerts = await callApi(page, "GET", `/api/v1/alerts/projects/${projectId}`);
    expect(alerts.status, JSON.stringify(alerts.body)).toBe(200);
    expect(alertCount(alerts.body), "the evaluation created or touched no alert").toBe(0);
    await page.getByRole("link", { name: "Coherence", exact: true }).first().click();
    await expect(page).toHaveURL(new RegExp(`/projects/${projectId}/coherence`), { timeout: 30_000 });
    await expect(page.getByRole("img", { name: /Coherence Score/i })).toHaveCount(0);

    // The two situations are different for the user AND for the API.
    expect(pending.status).not.toBe(empty.status);

    recorder.record("s3PendingContract", {
      projectId,
      documentId,
      emptyProjectId,
      pendingStatus: pending.status,
      emptyStatus: empty.status,
      scoreReason: result.score_reason,
      alertRows: alertCount(alerts.body),
    });
    recorder.write();
    await context.close();
  });
});
