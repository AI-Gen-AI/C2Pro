/**
 * TS-E2E-PJ01-001 — PJ-01 First Real User Journey, first half (shared harness acceptance).
 *
 * Login → Create Project → Upload Contract A → Processing → Health → six dimensions →
 * toward Evidence, on the deterministic PJ-01 Contract A fixture
 * (`test-data/pj01/contract-a.manifest.json`).
 *
 * Kept REAL, as in the P0b journey: Clerk auth, HTTP, the async worker, PostgreSQL, Redis,
 * the generated client and the browser. Only the AI/embedding provider may be deterministic.
 *
 * A technically green backend is not enough: the run fails (strict mode) when a step is not
 * reachable by visible navigation, when processing needs a manual refresh, shows success
 * before analysis completed, hides a backend error or spins indefinitely, or when Health
 * fabricates values. `PJ01_NAVIGATION_MODE=diagnostic` records such gaps and continues to
 * collect evidence, but can never produce a PJ-01 PASS.
 *
 * Evidence: `playwright/.pj01/<run-id>/run.json` + screenshots; project id in
 * `playwright/.pj01/project-id.txt`.
 */
import { expect, test } from "@playwright/test";

import { collectAttributableConsoleErrors } from "./support/pj01/console";
import { runPj01FirstHalf, runPj01SecondHalf } from "./support/pj01/journey";
import { ANALYSIS_BUDGET_MS } from "./support/pj01/processing";
import { Pj01RunRecorder } from "./support/pj01/run-recorder";

test.describe("TS-E2E-PJ01-001: PJ-01 first real user journey", () => {
  test.describe.configure({ mode: "serial", timeout: 2 * ANALYSIS_BUDGET_MS + 600_000 });

  test("login, project, Contract A, processing, Health, Evidence, revision B, What Changed?, Current State", async ({
    baseURL,
    page,
  }, testInfo) => {
    const recorder = Pj01RunRecorder.fromEnv();
    const consoleErrors = collectAttributableConsoleErrors(page);
    try {
      const first = await runPj01FirstHalf(page, { baseURL: baseURL ?? "http://localhost:3100", recorder });
      await runPj01SecondHalf(page, { recorder, first });
      recorder.record("attributableConsoleErrors", consoleErrors.length);
      expect(consoleErrors, "no attributable console errors").toEqual([]);
      expect(recorder.blockingFindings(), "no blocking PJ-01 findings").toEqual([]);
    } finally {
      const runFile = recorder.write();
      testInfo.annotations.push(
        { type: "pj01-classification", description: recorder.classification() },
        { type: "pj01-run", description: runFile },
      );
    }
  });
});
