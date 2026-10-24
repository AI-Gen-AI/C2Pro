/**
 * TS-E2E-TRIPLET-001 — one user, one project, three documents, one decision trail.
 *
 *   create project → upload contract → processing → HITL approval → upload budget and
 *   schedule → evaluate Coherence → Alerts / Health / Evidence → persistence
 *
 * WHAT IS REAL: the browser, the Next.js app, the FastAPI backend, PostgreSQL, the Celery
 * worker, the real .docx/.xlsx fixture files (test-data/triplet) and every request between
 * them. Nothing is route-mocked.
 *
 * WHAT IS NOT: the AI. This suite runs with C2PRO_AI_MOCK=1 / C2PRO_EMBEDDINGS_MOCK=1, so the
 * contract analysis returns "not assessed" and the human approval is REQUIRED, never skipped.
 * The journey records which mode it ran in and fails if the HITL gate was bypassed.
 *
 * WHAT IT DOES NOT PROVE: this is a three-document journey. It is not PQ-HITL-09 S1–S8: there is
 * no technical-specification family, no revision B / What Changed, no Clerk relogin (persistence
 * is checked from a fresh browser context restored from the saved session) and no cross-tenant
 * denial here.
 */
import { readFileSync } from "node:fs";
import path from "node:path";

import { expect, test, type Page } from "@playwright/test";

import { openProjects } from "./support/p0b-auth";
import { readProjectTabs } from "./support/pj01/health";
import { Pj01RunRecorder } from "./support/pj01/run-recorder";
import { uploadDocumentThroughUi } from "./support/pj01/upload";

const FIXTURE_DIR = path.join(process.cwd(), "src", "tests", "e2e", "test-data", "triplet");
const manifest = JSON.parse(readFileSync(path.join(FIXTURE_DIR, "triplet.manifest.json"), "utf8")) as {
  expected_rules: string[];
  contract: { completion_deadline: string };
};
const fixture = (name: string): string => path.join(FIXTURE_DIR, name);

const AI_IS_MOCKED = process.env.C2PRO_AI_MOCK === "1";
const runTag = `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`.toUpperCase();
const projectName = `Triplet Journey ${runTag}`;
const projectCode = `TJ${runTag}`;

const DOCUMENT_BUDGET_MS = 240_000;

/** Click the project tab whose link points at `/projects/{id}/<segment>` (tabs are links). */
async function openProjectTab(page: Page, projectId: string, segment: string): Promise<void> {
  const tabs = await readProjectTabs(page);
  const tab = tabs.find((candidate) => new RegExp(`/projects/${projectId}/${segment}(?:[/?#]|$)`).test(candidate.href));
  expect(tab, `a visible "${segment}" project tab (tabs: ${tabs.map((t) => t.name).join(", ")})`).toBeTruthy();
  await page.locator(`nav[aria-label="Project tabs"] a[href="${tab?.href}"]`).first().click();
  await page.waitForURL(new RegExp(`/projects/${projectId}/${segment}`), { timeout: 30_000 });
}

function documentRow(page: Page, filename: string) {
  return page
    .getByTestId(/^document-row-/)
    .filter({ has: page.getByTestId("document-name").filter({ hasText: filename }) });
}

async function expectDocumentState(page: Page, filename: string, state: RegExp): Promise<void> {
  await expect(
    documentRow(page, filename).getByTestId("document-status-badge"),
    `${filename} must reach ${state} without a manual reload`,
  ).toHaveText(state, { timeout: DOCUMENT_BUDGET_MS });
}

async function createProjectThroughWizard(page: Page): Promise<string> {
  await openProjects(page);
  await page.goto("/projects/new");
  await expect(page).toHaveURL(/\/projects\?create=1/, { timeout: 30_000 });
  const wizard = page.getByRole("dialog", { name: "Create project" });
  await expect(wizard).toBeVisible();
  await wizard.getByTestId("project-name-input").fill(projectName);
  await wizard.getByTestId("project-code-input").fill(projectCode);
  await wizard.getByTestId("project-type-select").selectOption("building");
  await wizard.getByRole("button", { name: "Next step" }).click();
  await wizard.getByTestId("client-name-input").fill("Triplet Journey Client");
  await wizard.getByTestId("currency-select").selectOption("EUR");
  await wizard.getByRole("button", { name: "Review project" }).click();
  await expect(wizard.getByTestId("review-name")).toHaveText(projectName);
  await wizard.getByRole("button", { name: "Create project", exact: true }).click();
  await expect(page).toHaveURL(/\/projects\/[0-9a-f-]{36}\/documents/, { timeout: 60_000 });
  await expect(page.getByTestId("documents-page")).toBeVisible({ timeout: 30_000 });
  const projectId = page.url().match(/\/projects\/([0-9a-f-]{36})\//)?.[1];
  if (!projectId) throw new Error("TRIPLET_PROJECT_ID_UNRESOLVED");
  return projectId;
}

type EvaluatedAlert = { rule_id?: string; severity?: string; message?: string };

test.describe("TS-E2E-TRIPLET-001: contract → HITL → budget + schedule → coherence → persistence", () => {
  test(`AI ${AI_IS_MOCKED ? "MOCKED" : "NOT mocked"}: the triplet raises budget and schedule alerts`, async ({
    page,
    browser,
  }) => {
    test.setTimeout(900_000);
    test.info().annotations.push({
      type: "ai",
      description: AI_IS_MOCKED
        ? "MOCKED: C2PRO_AI_MOCK=1, C2PRO_EMBEDDINGS_MOCK=1 — no Claude call is exercised"
        : "NOT mocked: a real model is in the loop",
    });
    const recorder = Pj01RunRecorder.fromEnv();
    recorder.record("aiMocked", AI_IS_MOCKED);

    // 1 ── a user creates a project
    const projectId = await test.step("create the project through the wizard", () =>
      createProjectThroughWizard(page));

    // 2 ── uploads the contract and waits for it, without reloading
    const contract = await test.step("upload the contract", () =>
      uploadDocumentThroughUi(page, recorder, {
        projectId,
        filePath: fixture("triplet-contract.docx"),
        documentType: "contract",
      }));

    // 3 ── the contract needs a human decision (the HITL gate must not be bypassed)
    await test.step("the contract waits for human review", async () => {
      await expectDocumentState(page, "triplet-contract.docx", /review required|analy[sz]ed/i);
      const badge = await documentRow(page, "triplet-contract.docx")
        .getByTestId("document-status-badge")
        .innerText();
      if (AI_IS_MOCKED) {
        expect(badge, "with the AI mocked the analysis is 'not assessed': approval is required").toMatch(
          /review required/i,
        );
      }
      recorder.record("contractStateBeforeApproval", badge);
    });

    await test.step("approve the contract in the review queue (HITL)", async () => {
      const cta = documentRow(page, "triplet-contract.docx").getByTestId("document-review-cta");
      if ((await cta.count()) === 0) {
        // Real AI may analyse without a review; with the mock this branch is a failure above.
        return;
      }
      await cta.first().click();
      await expect(page.getByTestId("review-page")).toBeVisible({ timeout: 30_000 });
      const approve = page.locator('[data-testid^="approve-"]').first();
      await expect(approve, "a review item with an approve action").toBeVisible({ timeout: 60_000 });
      await expect(approve).toBeEnabled({ timeout: 120_000 });
      const approved = page.waitForResponse(
        (response) =>
          response.request().method() === "POST" && /\/hitl\/queue\/[^/]+\/approve/.test(response.url()),
        { timeout: 120_000 },
      );
      await approve.click();
      await expect(page.getByRole("dialog", { name: /approve review item/i })).toBeVisible();
      await page.getByRole("button", { name: /confirm approve/i }).click();
      const response = await approved;
      expect(response.status(), "the approval must be accepted").toBeLessThan(300);
      recorder.record("hitlApprovalStatus", response.status());
    });

    await test.step("the approved contract finishes analysis and persists", async () => {
      await openProjectTab(page, projectId, "documents");
      await expectDocumentState(page, "triplet-contract.docx", /analy[sz]ed/i);
    });

    // 4 ── uploads the budget and the schedule
    await test.step("upload the budget", () =>
      uploadDocumentThroughUi(page, recorder, {
        projectId,
        filePath: fixture("triplet-budget.xlsx"),
        documentType: "budget",
      }));
    await test.step("upload the schedule", () =>
      uploadDocumentThroughUi(page, recorder, {
        projectId,
        filePath: fixture("triplet-schedule.xlsx"),
        documentType: "schedule",
      }));
    await test.step("budget and schedule finish processing", async () => {
      await expectDocumentState(page, "triplet-budget.xlsx", /analy[sz]ed|parsed/i);
      await expectDocumentState(page, "triplet-schedule.xlsx", /analy[sz]ed|parsed/i);
    });

    // 5 ── evaluates Coherence
    const evaluated = await test.step("evaluate coherence", async () => {
      await openProjectTab(page, projectId, "coherence");
      const evaluateButton = page.getByRole("button", { name: /^evaluate coherence$/i });
      await expect(evaluateButton, "the triplet is complete: evaluation is available").toBeEnabled({
        timeout: 60_000,
      });
      const answered = page.waitForResponse(
        (response) =>
          response.request().method() === "POST" && /\/coherence\/evaluate/.test(response.url()),
        { timeout: 180_000 },
      );
      await evaluateButton.click();
      const response = await answered;
      expect(response.status(), "coherence evaluation must succeed").toBeLessThan(300);
      return (await response.json()) as { alerts?: EvaluatedAlert[]; overall_score?: number | null };
    });

    await test.step("the evaluation names every expected discrepancy", () => {
      const rules = new Set((evaluated.alerts ?? []).map((alert) => alert.rule_id));
      for (const rule of manifest.expected_rules) {
        expect(rules, `${rule} must be raised by the triplet`).toContain(rule);
      }
      expect(
        evaluated.overall_score,
        "a score exists only when the evidence supports it; an unassessed score would hide alerts",
      ).not.toBeNull();
      recorder.record("evaluatedRules", [...rules]);
    });

    // 6 ── sees Alerts, Health and Evidence
    await test.step("Alerts lists the discrepancies", async () => {
      await openProjectTab(page, projectId, "alerts");
      await expect
        .poll(async () => page.locator("table tbody tr").count(), {
          message: "the Alerts table lists the raised alerts",
          timeout: 60_000,
        })
        .toBeGreaterThanOrEqual(manifest.expected_rules.length);
    });

    await test.step("Health is reachable and honest (no error state)", async () => {
      await openProjectTab(page, projectId, "(?:health|analysis)");
      await expect(page.getByRole("region", { name: "Document health" })).toBeVisible({ timeout: 60_000 });
      for (const state of ["health-error", "health-unavailable", "health-not-found"]) {
        await expect(page.getByTestId(state)).toHaveCount(0);
      }
    });

    await test.step("Evidence opens the contract the completion date came from", async () => {
      await openProjectTab(page, projectId, "documents");
      await documentRow(page, "triplet-contract.docx").getByRole("link").first().click();
      await page.waitForURL(new RegExp(`/projects/${projectId}/evidence\\?documentId=${contract.documentId}`), {
        timeout: 30_000,
      });
      await expect(page.getByText(/could not load|failed to load/i)).toHaveCount(0);
    });

    // 7 ── persistence: a brand-new browser context restored from the saved session
    await test.step("the state persists in a fresh browser context", async () => {
      const fresh = await browser.newContext({ storageState: "playwright/.auth/user.json" });
      try {
        const reopened = await fresh.newPage();
        await reopened.goto(`/projects/${projectId}/alerts`);
        await expect
          .poll(async () => reopened.locator("table tbody tr").count(), { timeout: 60_000 })
          .toBeGreaterThanOrEqual(manifest.expected_rules.length);
        await reopened.goto(`/projects/${projectId}/documents`);
        for (const name of ["triplet-contract.docx", "triplet-budget.xlsx", "triplet-schedule.xlsx"]) {
          await expect(documentRow(reopened, name)).toHaveCount(1);
        }
      } finally {
        await fresh.close();
      }
    });
  });
});
