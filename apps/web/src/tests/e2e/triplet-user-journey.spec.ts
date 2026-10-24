/**
 * TS-E2E-TRIPLET-001 — one user, one project, three documents, one decision trail.
 *
 *   create project → upload contract → processing → HITL approval → upload budget and
 *   schedule → evaluate Coherence → Alerts / Health / Evidence → persistence
 *
 * WHAT IS REAL: the browser, the Next.js app, the FastAPI backend, PostgreSQL, the Celery
 * worker, the real .pdf/.xlsx fixture files (test-data/triplet) and every request between
 * them. Nothing is route-mocked. The contract fixture is a PDF because the upload dialog accepts
 * only .pdf/.xlsx/.bc3 (a .docx contract, which the backend and the PQ-HITL-09 matrix accept, cannot
 * be uploaded from the UI).
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
  expected_provisional: string[];
  contract: { completion_deadline: string };
};
const fixture = (name: string): string => path.join(FIXTURE_DIR, name);

// The authentic PQ-HITL-09 / ACC-01 (#1049) matrix: step ids and titles come from it, never from this
// test. Every step stays NOT_VERIFIED for UAT; this journey only reports how much of each step it
// actually exercised.
const MATRIX_PATH = path.resolve(
  process.cwd(),
  "..",
  "api",
  "tests",
  "fixtures",
  "pq_hitl_09_multidoc_journey_matrix_v1.json",
);
const matrixSteps = (
  JSON.parse(readFileSync(MATRIX_PATH, "utf8")) as { scenarios: { step_id: string; title: string }[] }
).scenarios;
type StepCoverage = { state: "PARTIAL" | "NOT_EXERCISED"; note: string };
const coverage: Record<string, StepCoverage> = Object.fromEntries(
  matrixSteps.map((step) => [step.step_id, { state: "NOT_EXERCISED", note: "not part of this journey" } as StepCoverage]),
);
const markStep = (stepId: string, state: StepCoverage["state"], note: string): void => {
  coverage[stepId] = { state, note };
};

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

type PolledDocument = {
  id?: string;
  filename?: string;
  status?: string | null;
  lifecycle_status?: string | null;
  status_detail?: string | null;
};

/** Remember the latest documents-list answer the APP itself received (no extra requests). */
function trackDocumentsList(page: Page, projectId: string): () => PolledDocument[] {
  let latest: PolledDocument[] = [];
  const listPath = new RegExp(`/projects/${projectId}/documents/?$`);
  page.on("response", async (response) => {
    if (response.request().method() !== "GET" || !response.ok()) return;
    if (!listPath.test(new URL(response.url()).pathname)) return;
    try {
      const body = (await response.json()) as { items?: PolledDocument[] } | PolledDocument[];
      latest = Array.isArray(body) ? body : (body.items ?? []);
    } catch {
      // not a JSON list: leave the previous answer
    }
  });
  return () => latest;
}

/**
 * The contract's state AFTER the human approval. Distinguishes two different defects:
 * - it becomes "Analyzed" only after a manual reload  → the page does not self-update (UX finding);
 * - it never becomes "Analyzed", even after reloads    → the approval did not settle (hard failure,
 *   reported with the backend's own answer).
 */
async function expectApprovedDocumentSettled(
  page: Page,
  filename: string,
  latestList: () => PolledDocument[],
): Promise<void> {
  const badge = () => documentRow(page, filename).getByTestId("document-status-badge");
  const analysed = /analy[sz]ed/i;
  try {
    await expect(badge()).toHaveText(analysed, { timeout: 120_000 });
    return;
  } catch {
    test.info().annotations.push({
      type: "finding",
      description: `DOCUMENT_STATE_STALE_WITHOUT_RELOAD: ${filename} still read "${await badge()
        .innerText()
        .catch(() => "?")}" 120 s after the approval`,
    });
  }
  const deadline = Date.now() + 180_000;
  while (Date.now() < deadline) {
    await page.reload();
    await page.getByTestId("documents-page").waitFor({ state: "visible", timeout: 30_000 });
    const text = await badge().innerText({ timeout: 10_000 }).catch(() => "");
    if (analysed.test(text)) {
      test.info().annotations.push({
        type: "finding",
        description: `DOCUMENT_NEEDS_RELOAD: ${filename} is Analyzed on the server but the page did not show it without a reload`,
      });
      return;
    }
    await page.waitForTimeout(8_000);
  }
  const mine = latestList().find((item) => item.filename === filename);
  throw new Error(
    `TRIPLET_APPROVAL_NOT_SETTLED: ${filename} never became Analyzed after the approval. ` +
      `Backend list answer: ${JSON.stringify(mine ?? latestList().map((i) => i.filename))}`,
  );
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

    markStep(
      "S1",
      "PARTIAL",
      "project created through the UI under a RESTORED session (not a Clerk login); tenant isolation not exercised here",
    );

    const latestDocuments = trackDocumentsList(page, projectId);

    await test.step("S2: an unsupported file type is refused by the upload dialog and nothing is sent", async () => {
      const uploadPosts: string[] = [];
      const onRequest = (request: { method(): string; url(): string }): void => {
        if (
          request.method() === "POST" &&
          new RegExp(`/projects/${projectId}/documents/?$`).test(new URL(request.url()).pathname)
        ) {
          uploadPosts.push(request.url());
        }
      };
      page.on("request", onRequest);
      await page.getByRole("button", { name: /upload document/i }).click();
      const surface = page.getByTestId("document-upload-surface");
      await expect(surface).toBeVisible({ timeout: 15_000 });
      await page.setInputFiles('input[type="file"]', {
        name: "payload.bin",
        mimeType: "application/octet-stream",
        buffer: Buffer.from("not a project document"),
      });
      await expect(surface.getByText(/unsupported file type: \.bin/i)).toBeVisible({ timeout: 15_000 });
      page.off("request", onRequest);
      expect(uploadPosts, "a refused file must never reach the backend").toEqual([]);
      await page.keyboard.press("Escape");
      await expect(surface).toBeHidden({ timeout: 15_000 });
      test.info().annotations.push({
        type: "s2-scope",
        description: "UI gate only: the backend 415 for unsupported extensions is not exercised by this journey",
      });
    });

    // 2 ── uploads the contract and waits for it, without reloading
    const contract = await test.step("upload the contract", () =>
      uploadDocumentThroughUi(page, recorder, {
        projectId,
        filePath: fixture("triplet-contract.pdf"),
        documentType: "contract",
      }));

    // 3 ── the contract needs a human decision (the HITL gate must not be bypassed)
    await test.step("the contract waits for human review", async () => {
      await expectDocumentState(page, "triplet-contract.pdf", /review required|analy[sz]ed/i);
      const badge = await documentRow(page, "triplet-contract.pdf")
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
      const cta = documentRow(page, "triplet-contract.pdf").getByTestId("document-review-cta");
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
      const approvalBody = (await response.text().catch(() => "")).slice(0, 400);
      test.info().annotations.push({
        type: "hitl-approval",
        description: `HTTP ${response.status()} ${approvalBody}`,
      });
      expect(response.status(), `the approval must be accepted: ${approvalBody}`).toBeLessThan(300);
      recorder.record("hitlApprovalStatus", response.status());
    });

    await test.step("the approved contract finishes analysis and persists", async () => {
      await openProjectTab(page, projectId, "documents");
      await expectApprovedDocumentSettled(page, "triplet-contract.pdf", latestDocuments);
      markStep(
        "S5",
        "PARTIAL",
        "one review item approved by a human through the UI; ledger immutability and the optimistic-concurrency fence are not asserted here",
      );
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
      markStep(
        "S2",
        "PARTIAL",
        "contract, budget and schedule uploaded through the UI; no technical_spec family, no pinned revision hash check, UI gate only for rejection",
      );
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
      // A schedule date read from a submitted file is an observation, not an approved baseline: it
      // is shown as a PROVISIONAL advisory and must never appear as a confirmed breach.
      for (const rule of manifest.expected_provisional) {
        expect(rules, `${rule} must be shown as a provisional risk`).toContain(rule);
      }
      expect(rules, "a submitted schedule never confirms a breach").not.toContain("DET-CRS-SCHDEAD");
      // Three document families are not the four of PQ-HITL-09: with no technical specification
      // the coherence score is honestly WITHHELD. A withheld score must say why (AUDIT_INCOMPLETE);
      // a null score without a reason would be a hidden failure.
      if (evaluated.overall_score === null || evaluated.overall_score === undefined) {
        expect(rules, "a withheld score must be explained by AUDIT_INCOMPLETE").toContain("AUDIT_INCOMPLETE");
        test.info().annotations.push({
          type: "finding",
          description: "SCORE_WITHHELD_AUDIT_INCOMPLETE: no coherence score for contract + budget + schedule",
        });
      }
      recorder.record("evaluatedRules", [...rules]);
      markStep(
        "S3",
        "PARTIAL",
        `evaluation ran on three families; score ${evaluated.overall_score ?? "withheld (AUDIT_INCOMPLETE)"}; the six-dimension Health vector is not asserted dimension by dimension`,
      );
    });

    // 6 ── sees Alerts, Health and Evidence
    await test.step("Alerts lists the discrepancies", async () => {
      await openProjectTab(page, projectId, "alerts");
      // SOFT on purpose: /coherence/evaluate raises the discrepancies but only persists them to
      // the Alerts table when a score exists, so with the score withheld this page is empty.
      // That is a product gap the journey must keep reporting (red), not hide, while the
      // remaining steps still run.
      await expect
        .poll(async () => page.locator("table tbody tr").count(), {
          message:
            "ALERTS_NOT_PERSISTED: the evaluation raised the discrepancies but the Alerts table does not list them",
          timeout: 30_000,
        })
        .toBeGreaterThanOrEqual(manifest.expected_rules.length + manifest.expected_provisional.length)
        .catch((error: unknown) => {
          expect.soft(false, String(error)).toBe(true);
        });

      // S4: an alert must lead to its source. Only the clause link exists today (the XLSX row is named in
      // the evidence text, not linked), so this checks the clause -> evidence navigation.
      const evidenceLink = page.getByRole("link", { name: /^view evidence for /i }).first();
      if ((await evidenceLink.count()) === 0) {
        markStep("S4", "NOT_EXERCISED", "no alert row with an evidence link (ALERTS_NOT_PERSISTED)");
        return;
      }
      await evidenceLink.click();
      await page.waitForURL(new RegExp(`/projects/${projectId}/evidence\\?documentId=`), { timeout: 30_000 });
      await expect(page.getByText(/could not load|failed to load/i)).toHaveCount(0);
      markStep(
        "S4",
        "PARTIAL",
        "alert -> contract clause evidence page; the schedule row is not a first-class link and no WBS linkage is asserted",
      );
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
      await documentRow(page, "triplet-contract.pdf").getByRole("link").first().click();
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
          .poll(async () => reopened.locator("table tbody tr").count(), { timeout: 30_000 })
          .toBeGreaterThanOrEqual(manifest.expected_rules.length + manifest.expected_provisional.length)
          .catch((error: unknown) => {
            expect.soft(false, `ALERTS_NOT_PERSISTED (fresh context): ${String(error)}`).toBe(true);
          });
        await reopened.goto(`/projects/${projectId}/documents`);
        for (const name of ["triplet-contract.pdf", "triplet-budget.xlsx", "triplet-schedule.xlsx"]) {
          await expect(documentRow(reopened, name)).toHaveCount(1);
        }
        markStep(
          "S8",
          "PARTIAL",
          "state survives a fresh browser context restored from the saved session; no Clerk relogin, no cross-tenant denial (see pj01-tenant-isolation), no runtime SHA check",
        );
      } finally {
        await fresh.close();
      }
    });

    // The authentic matrix steps and how much of each this journey exercised. Nothing here is a UAT
    // result: every step stays NOT_VERIFIED until a real, non-mocked run is reviewed.
    await test.step("report PQ-HITL-09 step coverage (not a UAT result)", () => {
      markStep("S6", "NOT_EXERCISED", "no revision B, no What Changed / Current State comparison");
      markStep(
        "S7",
        "NOT_EXERCISED",
        "cross-document rules run, but there is no approved canonical WBS in this journey",
      );
      for (const step of matrixSteps) {
        const entry = coverage[step.step_id];
        test.info().annotations.push({
          type: `pq-hitl-09:${step.step_id}`,
          description: `${entry.state} — ${step.title} — ${entry.note}`,
        });
      }
      recorder.record("pqHitl09Coverage", coverage);
    });
  });
});
