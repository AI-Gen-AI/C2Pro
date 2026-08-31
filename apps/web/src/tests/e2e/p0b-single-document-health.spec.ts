/**
 * TS-E2E-P0B-HEALTH-001 — canonical P0b single-document Health journey.
 *
 * This is the acceptance gate for the P0b vertical: upload ONE contract and get
 * an honest, evidence-backed answer on screen.
 *
 * It exists because production failed silently in exactly the seam the previous
 * E2E coverage did not touch. A real contract reached `upload_status=analyzed`
 * with 25 persisted clauses, zero RAG chunks, zero analyses, zero project_events
 * and zero project_snapshots — and every existing check was green. The older
 * `document-analysis-pipeline.spec.ts` could not have caught it: it drives
 * `proj_demo_001` over demo routes that bypass Clerk and pre-seed their state,
 * so it never performs a real upload and never reaches the async seam.
 *
 * Therefore this journey deliberately keeps REAL: Clerk auth, HTTP, the async
 * worker, RAG chunk persistence, the N1-N17 graph, PostgreSQL, Redis, the
 * generated API client and the browser. Only the AI/embedding provider may be
 * made deterministic, and only at the provider/network boundary — never by
 * stubbing the seam that broke.
 *
 * The database-side assertions MASTER requires (clauses > 1, RAG chunks > 0,
 * analysis row, graph.completed event, project snapshot) are enforced by
 * `apps/api/scripts/verify_p0b_journey.py`, which CI runs immediately after
 * this spec against the project id written to `playwright/.p0b/project-id.txt`.
 * Splitting it that way keeps the DB assertions in the language that owns the
 * schema instead of adding a second Postgres client to the web package.
 */

import { existsSync, mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test, type ConsoleMessage, type Page } from "@playwright/test";

import {
  assertProjectEntryContinuity,
  establishAuthenticatedSession,
  observeAuth,
} from "./support/p0b-auth";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const CONTRACT_FIXTURE = path.join(HERE, "test-data", "sample-contract.pdf");
const PROJECT_ID_OUTPUT = path.join(process.cwd(), "playwright", ".p0b", "project-id.txt");

/** Analysis is a real async pipeline; it is slow, not instant. */
const ANALYSIS_TIMEOUT_MS = 240_000;

const CANONICAL_CATEGORIES = [
  "SCOPE",
  "BUDGET",
  "TIME",
  "TECHNICAL",
  "LEGAL",
  "QUALITY",
] as const;

function recordProjectId(projectId: string): void {
  const dir = path.dirname(PROJECT_ID_OUTPUT);
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
  writeFileSync(PROJECT_ID_OUTPUT, projectId, "utf8");
}

/** Console errors attributable to the app, ignoring third-party noise. */
function collectConsoleErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("console", (message: ConsoleMessage) => {
    if (message.type() !== "error") return;
    const text = message.text();
    // Clerk/telemetry/network chatter is not an L4-5 regression signal.
    if (/clerk|telemetry|favicon|analytics|third-party/i.test(text)) return;
    errors.push(text);
  });
  return errors;
}

test.describe("TS-E2E-P0B-HEALTH-001: single-document Health journey", () => {
  test.describe.configure({ mode: "serial", timeout: ANALYSIS_TIMEOUT_MS + 120_000 });

  test("upload one contract and see honest, evidence-backed Health", async ({
    baseURL,
    page,
  }) => {
    const consoleErrors = collectConsoleErrors(page);
    const observation = observeAuth(page, baseURL ?? "http://localhost:3100");

    // --- 1. Real Clerk authentication, performed LIVE in this page and context
    //        with the documented @clerk/testing flow. No storageState restore,
    //        no password, no credential literal.
    await establishAuthenticatedSession(page, observation);

    // --- 2. Project entry is gated INLINE, in this same test/page/context,
    //        before any project creation, upload or worker-dependent work. A
    //        separate spec could not license this run: separate Playwright tests
    //        get separate browser contexts. It proves Clerk session, Clerk user,
    //        expected Organization, application bearer, route and API auth
    //        health together, fails fast with a classification instead of
    //        burning the journey timeout, and leaves the dialog open and
    //        editable so the journey continues from that exact state.
    await assertProjectEntryContinuity(page, observation);

    // --- 3. A clean project, so no prior snapshot or document can contaminate.
    const projectName = `P0b Health Journey ${Date.now()}`;
    await page.getByTestId("project-name-input").fill(projectName);
    await page.getByTestId("create-project-button").click();

    await page.waitForURL(/\/projects\/[0-9a-f-]{36}/, { timeout: 60_000 });
    const projectId = page.url().match(/\/projects\/([0-9a-f-]{36})/)?.[1];
    expect(projectId, "project id must be resolvable from the URL").toBeTruthy();
    recordProjectId(projectId!);

    // --- 5. Upload one real contract through the real upload surface.
    await page.goto(`/projects/${projectId}/documents`);
    await expect(page.getByTestId("documents-page")).toBeVisible({ timeout: 30_000 });
    await page.setInputFiles('input[type="file"]', CONTRACT_FIXTURE);

    // --- 6. Wait for the async pipeline. The Health call is the completion
    //        signal: it is the thing the user is actually waiting for.
    const healthResponsePromise = page.waitForResponse(
      (response) =>
        /\/projects\/[0-9a-f-]{36}\/health/.test(response.url()) && response.status() === 200,
      { timeout: ANALYSIS_TIMEOUT_MS },
    );

    await page.goto(`/projects/${projectId}/analysis`);
    const healthResponse = await healthResponsePromise;

    // --- 7. /health = 200 with the real single-document payload.
    expect(healthResponse.status()).toBe(200);
    const vector = await healthResponse.json();

    expect(vector.single_document_coverage, "single_document_coverage must exist").toBeTruthy();
    const assessments = vector.single_document_coverage.assessments ?? [];
    expect(assessments).toHaveLength(6);
    expect(new Set(assessments.map((a: { category: string }) => a.category))).toEqual(
      new Set(CANONICAL_CATEGORIES),
    );

    const granularity = vector.single_document_evidence_granularity;
    expect(granularity, "granularity must be disclosed, not inferred").toBeTruthy();

    // Evidence ids must be persisted clause UUIDs when granularity is clause-level.
    if (granularity === "clause") {
      const evidenceIds = assessments.flatMap(
        (a: { evidence_clause_ids?: string[] }) => a.evidence_clause_ids ?? [],
      );
      expect(evidenceIds.length, "clause granularity must carry clause ids").toBeGreaterThan(0);
      for (const id of evidenceIds) {
        expect(id).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/);
      }
    }

    // --- 8. The user-visible surface.
    const health = page.getByTestId("single-document-health");
    await expect(health).toBeVisible({ timeout: 60_000 });

    for (const category of CANONICAL_CATEGORIES) {
      await expect(
        page.getByTestId(`health-category-${category}`),
        `${category} tile must render`,
      ).toBeVisible();
    }

    // --- 9. Honest null: never 0%, never a fabricated measured score.
    const healthText = (await health.innerText()) ?? "";
    expect(healthText, "INV-1: unknown must never render as 0%").not.toMatch(/\b0\s*%/);

    const unknownTiles = page.getByText("Unknown / Insufficient evidence");
    if ((await unknownTiles.count()) > 0) {
      // An insufficient category must say what is missing and what to do.
      await expect(page.getByTestId("health-missing-data").first()).toBeVisible();
      await expect(page.getByTestId("health-gap").first()).toBeVisible();
    }

    // --- 10. Granularity disclosed in the UI, matching the API's claim.
    const granularityText = await page.getByTestId("health-granularity").innerText();
    if (granularity === "clause") {
      expect(granularityText).toMatch(/clause-level/i);
    } else if (granularity === "document") {
      expect(granularityText).toMatch(/whole-document/i);
    }

    // --- 11. Coherence: a number only when positive evidence says it is available.
    const coherenceShown = await page.getByTestId("analysis-coherence-score").count();
    const coherenceSuppressed = await page.getByTestId("analysis-coherence-unavailable").count();
    expect(
      coherenceShown + coherenceSuppressed,
      "exactly one Coherence state must render",
    ).toBe(1);

    const contractDimension = (vector.dimensions ?? []).find(
      (d: { dimension: string }) => d.dimension === "CONTRACT",
    );
    const hasSubscoreEvidence = (contractDimension?.evidence ?? []).some(
      (ref: { ref_id: string }) => ref.ref_id === "project-coherence-subscore",
    );
    expect(
      coherenceShown === 1,
      "a Coherence number may render only with incorporated-subscore evidence",
    ).toBe(hasSubscoreEvidence);

    // --- 12. Terminal UX: nothing still claiming to be in progress.
    await expect(page.getByTestId("health-loading")).toHaveCount(0);
    await expect(page.getByTestId("health-error")).toHaveCount(0);
    await expect(page.getByTestId("health-unavailable")).toHaveCount(0);
    await expect(page.getByText(/finalizing/i)).toHaveCount(0);
    await expect(page.locator(".animate-spin")).toHaveCount(0);

    // --- 13. No console exception attributable to this surface.
    expect(consoleErrors, "no attributable console errors").toEqual([]);
  });
});
