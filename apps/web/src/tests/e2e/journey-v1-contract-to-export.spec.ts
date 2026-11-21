/**
 * JV1-A23 / L8 — RED phase, contract-driven synthetic browser acceptance.
 *
 * A1 is the interface oracle (N4Coverage and N4SharedFinding). This spec deliberately
 * asserts behaviour planned for A15–A22/A26 that does not exist on the base branch.
 * It must not be marked test.fail(), softened, or counted as green acceptance.
 *
 * Live browser + disposable Clerk DEVELOPMENT tenant + disposable DB/worker.
 * Only committed synthetic PJ-01 input is uploaded. No provider, pilot account,
 * production credentials, request interception, seeded success response or LLM call.
 *
 * Explicit opt-in: JV1_A23_RED_RUN=1. Preflight fails closed unless the operator
 * certifies the disposable runtime; the ordinary Chromium suite skips these tests.
 */
import { readFileSync } from "node:fs";
import path from "node:path";

import { expect, test, type Browser, type Page } from "@playwright/test";

import { signInAsJourneyUser, createProjectThroughUi } from "./support/pj01/session";
import { uploadDocumentThroughUi } from "./support/pj01/upload";
import { observeProcessingWithoutReload } from "./support/pj01/processing";
import { Pj01RunRecorder } from "./support/pj01/run-recorder";

const EMPTY_STORAGE = { cookies: [], origins: [] };
const SYNTHETIC_PDF = path.join(process.cwd(), "src/tests/e2e/test-data/pj01/contract-a.pdf");
const SYNTHETIC_TEXT = readFileSync(
  path.join(process.cwd(), "src/tests/e2e/test-data/pj01/contract-a.source.txt"),
  "utf8",
);
const DIMENSIONS = ["SCOPE", "BUDGET", "TIME", "LEGAL", "QUALITY", "TECHNICAL"];
const SEVERITIES = ["CRITICAL", "HIGH", "MEDIUM", "LOW"];
const GAP_FAILURES = [
  "OUTPUT_TRUNCATED", "INVALID_ENVELOPE", "PROVIDER_REJECTED_UNBILLED",
  "PROVIDER_RESULT_UNCERTAIN", "BUDGET_UNAVAILABLE",
];
const CONTRACT_VERSION = "n4-coverage-v1";

type Row = Record<string, unknown>;
const record = (value: unknown): Row =>
  value !== null && typeof value === "object" && !Array.isArray(value)
    ? value as Row
    : {};
const rows = (value: unknown): Row[] =>
  Array.isArray(value) ? value.map(record) : [];
const compact = (value: string): string => value.replace(/\s+/g, " ").trim();

interface ApiAnswer {
  status: number;
  body: unknown;
}

/** Browser-owned Clerk JWT; never serialize, log or attach it to test evidence. */
async function authenticatedGet(page: Page, url: string): Promise<ApiAnswer> {
  return page.evaluate(async (target) => {
    const jwt = await window.Clerk?.session?.getToken();
    if (!jwt) throw new Error("A23_DISPOSABLE_CLERK_SESSION_MISSING");
    const response = await fetch(target, { headers: { Authorization: `Bearer ${jwt}` }, cache: "no-store" });
    const body: unknown = await response.json().catch(() => null);
    return { status: response.status, body };
  }, url);
}

async function documentFindings(page: Page, projectId: string, documentId: string): Promise<Row> {
  const answer = await authenticatedGet(
    page, `/api/v1/projects/${projectId}/documents/${documentId}/n4-findings`,
  );
  expect(answer.status, "A1-backed N4 findings must be readable for the owning Clerk tenant").toBe(200);
  return record(answer.body);
}

/** A1 frozen schema, not the older count-only UI coverage shape. */
function expectA1Coverage(body: Row, status: "COMPLETE" | "COMPLETE_WITH_GAPS"): Row {
  const coverage = record(body.n4_coverage ?? record(body.coverage).n4_coverage ?? body.coverage);
  expect(coverage.schema_version, "A1 n4-coverage-v1 schema").toBe(CONTRACT_VERSION);
  expect(coverage.status, "derived coverage state, not ledger database status").toBe(status);
  expect(coverage.run_id).toMatch(/^[0-9a-f-]{36}$/i);
  expect(coverage.source_sha256).toMatch(/^[a-f0-9]{64}$/);
  expect(coverage.total_windows).toEqual(expect.any(Number));
  expect(coverage.examined_windows).toEqual(expect.any(Number));
  expect(Array.isArray(coverage.gap_windows), "A1 gap window ordinals").toBe(true);
  expect(Array.isArray(coverage.gaps), "A1 gap details").toBe(true);
  return coverage;
}

/** No test may contact the pilot or use a production Clerk key by accident. */
function requireDisposableRuntime(baseURL: string): void {
  const required: Record<string, string> = {
    JV1_A23_DISPOSABLE: "1",
    ENVIRONMENT: "test",
    C2PRO_AI_MOCK: "1",
  };
  for (const [name, expected] of Object.entries(required)) {
    expect(process.env[name], `A23 safety gate: ${name} must be ${expected}`).toBe(expected);
  }
  expect(process.env.E2E_CLERK_USER_EMAIL, "explicit disposable Clerk test user; never use helper fallback").toBeTruthy();
  expect(process.env.E2E_CLERK_ORGANIZATION_ID, "explicit disposable Clerk development organization").toBeTruthy();
  const key = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY ?? "";
  expect(key.startsWith("pk_test_"), "production Clerk publishing keys are prohibited").toBe(true);
  const origin = new URL(baseURL);
  expect(["localhost", "127.0.0.1", "::1"].includes(origin.hostname),
    "A23 must point to a locally served disposable web, never a deployed pilot").toBe(true);
  for (const keyName of ["API_URL", "NEXT_PUBLIC_API_URL", "BACKEND_URL"]) {
    const raw = process.env[keyName];
    if (raw) {
      const host = new URL(raw).hostname;
      expect(["localhost", "127.0.0.1", "::1"].includes(host),
        `A23 safety gate: ${keyName} must resolve to disposable localhost`).toBe(true);
    }
  }
}

async function newTestSession(browser: Browser, baseURL: string) {
  const context = await browser.newContext({ baseURL, storageState: EMPTY_STORAGE });
  const page = await context.newPage();
  const auth = await signInAsJourneyUser(page, baseURL);
  return { page, auth, close: () => context.close() };
}

async function artifactMagic(page: Page, url: string): Promise<{ status: number; contentType: string; bytes: number; magic: number[] }> {
  return page.evaluate(async (target) => {
    const jwt = await window.Clerk?.session?.getToken();
    if (!jwt) throw new Error("A23_DISPOSABLE_CLERK_SESSION_MISSING");
    const response = await fetch(target, { headers: { Authorization: `Bearer ${jwt}` }, cache: "no-store" });
    const body = new Uint8Array(await response.arrayBuffer());
    return {
      status: response.status,
      contentType: response.headers.get("content-type") ?? "",
      bytes: body.length,
      magic: Array.from(body.subarray(0, 8)),
    };
  }, url);
}

test.describe("JV1-A23 RED: synthetic contract → decisions → score → exports → Clerk relogin", () => {
  test.skip(process.env.JV1_A23_RED_RUN !== "1",
    "TDD RED opt-in only; CI default must not touch Clerk, worker, DB or AI");

  test("COMPLETE: upload, literal page citations, independent decisions, score, XLSX/PDF and durable relogin", async ({ browser, baseURL }) => {
    test.setTimeout(720_000);
    const base = baseURL ?? "http://localhost:3100";
    requireDisposableRuntime(base);
    const first = await newTestSession(browser, base);
    let second: Awaited<ReturnType<typeof newTestSession>> | undefined;
    const recorder = new Pj01RunRecorder({ mode: "strict" });
    try {
      const { page } = first;
      const projectId = await createProjectThroughUi(page, first.auth, `JV1-A23-SYNTHETIC-${Date.now()}`);
      const { documentId, taskId } = await uploadDocumentThroughUi(page, recorder, {
        projectId, filePath: SYNTHETIC_PDF, documentType: "contract",
      });
      expect(taskId, "real disposable worker accepted the synthetic upload").toBeTruthy();

      const processing = await observeProcessingWithoutReload(page, recorder, {
        projectId, documentId, settlement: "review_required", budgetMs: 180_000,
        label: "A23 synthetic contract (without reload)",
      });
      expect(processing.evaluation.violations).toEqual([]);
      expect(processing.evaluation.outcome).toBe("review_required");

      const response = await documentFindings(page, projectId, documentId);
      const coverage = expectA1Coverage(response, "COMPLETE");
      expect(coverage.gap_windows).toEqual([]);
      expect(coverage.gaps).toEqual([]);
      const findings = rows(response.findings);
      expect(findings.length, "A23's synthetic scenario needs two independent reviewable findings").toBeGreaterThanOrEqual(2);
      for (const finding of findings) {
        expect(DIMENSIONS).toContain(finding.dimension);
        expect(SEVERITIES).toContain(finding.severity_proposed);
        expect(finding.review_state).toBe("PROPOSED");
        expect(typeof finding.source_quote).toBe("string");
        const quote = compact(String(finding.source_quote ?? ""));
        expect(quote.length, "literal source evidence is mandatory").toBeGreaterThan(10);
        expect(compact(SYNTHETIC_TEXT), "cited words must exist in synthetic source, not model interpretation").toContain(quote);
        expect(finding.page_start, "N4SharedFinding needs an actual PDF page").toEqual(expect.any(Number));
        expect(Number(finding.page_start)).toBeGreaterThan(0);
        expect(Number(finding.page_end)).toBeGreaterThanOrEqual(Number(finding.page_start));
      }

      await page.goto(`/projects/${projectId}/documents/${documentId}/n4-findings`);
      await expect(page.getByTestId("n4-proposed-finding")).toHaveCount(findings.length);
      // Decision must be available *within each finding*; read-only / bulk-only is RED.
      const cards = page.getByTestId("n4-proposed-finding");
      for (let index = 0; index < findings.length; index++) {
        const action = index === 1 ? /reject/i : /approve/i;
        await cards.nth(index).getByRole("button", { name: action }).click();
        const dialog = page.getByRole("dialog");
        await expect(dialog, "an explicit, attributable decision confirmation").toBeVisible();
        if (index === 1) {
          const reason = dialog.getByRole("textbox", { name: /reason/i });
          await expect(reason, "rejection requires a recorded reason").toBeVisible();
          await reason.fill("Synthetic A23 false positive, rejected in disposable test");
        }
        await dialog.getByRole("button", { name: /confirm|approve|reject/i }).last().click();
      }
      const decided = await documentFindings(page, projectId, documentId);
      expect(rows(decided.findings).filter((item) => item.review_state === "PROPOSED")).toHaveLength(0);
      await page.getByRole("button", { name: /final approval|finalize review|approve all/i }).click();

      const scoreUrl = `/api/v1/coherence/dashboard/${projectId}`;
      await expect.poll(async () => {
        const scored = await authenticatedGet(page, scoreUrl);
        const body = record(scored.body);
        return { status: scored.status, evaluated: Boolean(body.last_updated) };
      }, { timeout: 90_000 }).toEqual({ status: 200, evaluated: true });
      const afterApproval = await documentFindings(page, projectId, documentId);
      const score = record((await authenticatedGet(page, scoreUrl)).body);
      expect(Object.keys(record(score.sub_scores)).sort()).toEqual([...DIMENSIONS].sort());
      expect(score.validated_score, "validated score computed from confirmed facts").toEqual(expect.any(Number));
      expect(score.projected_score, "projected score computed separately").toEqual(expect.any(Number));

      const xlsx = await artifactMagic(page, `/api/v1/projects/${projectId}/reports/journey.xlsx`);
      const pdf = await artifactMagic(page, `/api/v1/projects/${projectId}/reports/journey.pdf`);
      expect(xlsx.status).toBe(200);
      expect(xlsx.magic.slice(0, 4), "genuine XLSX ZIP, not HTML/print view").toEqual([80, 75, 3, 4]);
      expect(pdf.status).toBe(200);
      expect(pdf.magic.slice(0, 4), "genuine PDF, not HTML/print view").toEqual([37, 80, 68, 70]);
      expect(xlsx.bytes).toBeGreaterThan(200);
      expect(pdf.bytes).toBeGreaterThan(200);

      const originalUser = await page.evaluate(() => window.Clerk?.user?.id ?? "");
      expect(originalUser).toBeTruthy();
      await page.getByRole("button", { name: "User menu" }).click();
      await page.getByRole("menuitem", { name: /sign out/i }).click();
      await expect(page).toHaveURL(/\/sign-in/);
      expect(await page.evaluate(() => Boolean(window.Clerk?.session))).toBe(false);

      second = await newTestSession(browser, base);
      const again = second.page;
      const newUser = await again.evaluate(() => window.Clerk?.user?.id ?? "");
      expect(newUser).toBe(originalUser);
      let reprocessWrites = 0;
      again.on("request", (request) => {
        if (request.method() === "POST" && /reprocess|analy[sz]e|ingest/i.test(new URL(request.url()).pathname)) {
          reprocessWrites += 1;
        }
      });
      await again.goto(`/projects/${projectId}/documents/${documentId}/n4-findings`);
      await expect(again.getByTestId("n4-proposed-finding")).toHaveCount(findings.length);
      const persisted = await documentFindings(again, projectId, documentId);
      const againCoverage = expectA1Coverage(persisted, "COMPLETE");
      expect(againCoverage.run_id, "relogin must not create another N4 run").toBe(coverage.run_id);
      expect(againCoverage.source_sha256).toBe(coverage.source_sha256);
      expect(rows(persisted.findings).map((item) => item.review_state))
        .toEqual(rows(afterApproval.findings).map((item) => item.review_state));
      expect(record((await authenticatedGet(again, scoreUrl)).body)).toMatchObject({
        validated_score: score.validated_score, projected_score: score.projected_score,
      });
      expect(reprocessWrites, "browser reopening never retriggers analysis").toBe(0);
      // A provider-side invocation count needs a separate disposable-worker ledger probe;
      // stable run ID and zero browser writes alone do NOT prove no backend LLM calls.
    } finally {
      await second?.close();
      await first.close();
    }
  });

  test("COMPLETE_WITH_GAPS: persisted open section blocks final approval and validated score", async ({ browser, baseURL }) => {
    test.setTimeout(180_000);
    const base = baseURL ?? "http://localhost:3100";
    requireDisposableRuntime(base);
    // A3/A7 own synthetic window failure injection; A23 must NOT mutate the
    // ledger or seed an apparently successful backend response from Playwright.
    // Disposable fixture IDs are created outside the repo by the test setup.
    const fixturePath = process.env.JV1_A23_GAPS_FIXTURE_FILE;
    expect(fixturePath, "A23 requires a disposable PG fixture from A3/A7, not pilot identifiers").toBeTruthy();
    const fixture = record(JSON.parse(readFileSync(fixturePath!, "utf8")) as unknown);
    expect(fixture.mode).toBe("SYNTHETIC_N4_NO_MODEL");
    expect(fixture.source_sha256).toMatch(/^[a-f0-9]{64}$/);
    const projectId = String(fixture.project_id ?? "");
    const documentId = String(fixture.document_id ?? "");
    expect(projectId).toMatch(/^[0-9a-f-]{36}$/i);
    expect(documentId).toMatch(/^[0-9a-f-]{36}$/i);

    const first = await newTestSession(browser, base);
    try {
      const { page } = first;
      const findings = await documentFindings(page, projectId, documentId);
      const coverage = expectA1Coverage(findings, "COMPLETE_WITH_GAPS");
      const gaps = rows(coverage.gaps);
      expect(gaps.length).toBeGreaterThan(0);
      expect(coverage.gap_windows).toEqual(gaps.map((gap) => gap.ordinal));
      for (const gap of gaps) {
        expect(GAP_FAILURES).toContain(gap.failure_kind);
        expect(gap.resolution).toBe("OPEN");
        expect(gap.attempts).toEqual(expect.any(Number));
        expect(gap.reason).toBeTruthy();
      }
      expect(rows(findings.findings).length, "the examined windows remain individually reviewable").toBeGreaterThan(0);

      await page.goto(`/projects/${projectId}/documents/${documentId}/n4-findings`);
      await expect(page.getByTestId("n4-proposed-finding").first()).toBeVisible();
      await expect(page.getByText(/section.*not analyzed|coverage gaps|pending.*section/i).first()).toBeVisible();
      await expect(page.getByRole("button", { name: /final approval|finalize review|approve all/i }))
        .toBeDisabled();
      await expect(page.getByTestId("n4-proposed-finding").first()
        .getByRole("button", { name: /reject/i })).toBeEnabled();

      const scored = await authenticatedGet(page, `/api/v1/coherence/dashboard/${projectId}`);
      expect(scored.status).toBe(200);
      const dashboard = record(scored.body);
      expect(dashboard.validated_score, "an open gap must never look like a verified 100").toBeNull();
      expect(dashboard.score_reason).toBe("n4_coverage_gaps");
      expect(Number(dashboard.pending_windows)).toBeGreaterThan(0);
      await page.reload();
      const persisted = expectA1Coverage(await documentFindings(page, projectId, documentId), "COMPLETE_WITH_GAPS");
      expect(persisted.run_id).toBe(coverage.run_id);
      expect(persisted.gaps).toEqual(coverage.gaps);
    } finally {
      await first.close();
    }
  });
});
