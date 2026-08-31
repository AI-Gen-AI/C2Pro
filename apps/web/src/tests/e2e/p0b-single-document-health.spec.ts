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
const HEALTH_POLL_INTERVAL_MS = 5_000;

/** Load the analysis page and return the health vector it fetched. */
async function loadHealthVector(page: Page, projectId: string): Promise<HealthVector> {
  const responsePromise = page.waitForResponse(
    (response) =>
      /\/projects\/[0-9a-f-]{36}\/health/.test(response.url()) && response.status() === 200,
    { timeout: 60_000 },
  );
  await page.goto(`/projects/${projectId}/analysis`);
  return (await responsePromise).json() as Promise<HealthVector>;
}

/** The serialized health vector, as far as this journey inspects it. */
interface HealthVector {
  single_document_coverage?: { assessments?: CategoryAssessment[] } | null;
  single_document_evidence_granularity?: string | null;
  dimensions?: { dimension: string; evidence?: { ref_id: string }[] }[];
}

/** The serialized shape of one CategoryAssessment (single_document_coverage.py). */
interface CategoryAssessment {
  category: string;
  state: string;
  evidence_count?: number;
  evidence_clause_ids?: string[];
  missing_data?: string[];
  gap?: unknown;
}

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

/**
 * Console errors attributable to the app, ignoring third-party noise.
 *
 * The ignore list is deliberately narrow and named: anything genuinely
 * attributable to this surface -- including CORS and other network failures --
 * must still fail the journey.
 */
const IGNORED_CONSOLE_NOISE = [
  // Clerk/telemetry/analytics chatter is not an L4-5 regression signal.
  /clerk|telemetry|favicon|analytics|third-party/i,
  // Emitted by Next's dev renderer on every page of every lane, including the
  // green E2E smoke lane. Not produced by any component this journey exercises.
  /Encountered a script tag while rendering React component/i,
];

function collectConsoleErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("console", (message: ConsoleMessage) => {
    if (message.type() !== "error") return;
    const text = message.text();
    if (IGNORED_CONSOLE_NOISE.some((pattern) => pattern.test(text))) return;
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

    //     CreateProjectWizard is a real 3-step wizard: only the name is
    //     required, and create-project-button renders solely on the review
    //     step. Drive it the way a user does rather than reaching for the
    //     submit button that does not exist yet.
    await page.getByRole("button", { name: "Next step" }).click();
    await page.getByRole("button", { name: "Review project" }).click();
    const createButton = page.getByTestId("create-project-button");
    await expect(createButton).toBeEnabled({ timeout: 15_000 });
    await createButton.click();

    await page.waitForURL(/\/projects\/[0-9a-f-]{36}/, { timeout: 60_000 });
    const projectId = page.url().match(/\/projects\/([0-9a-f-]{36})/)?.[1];
    expect(projectId, "project id must be resolvable from the URL").toBeTruthy();
    recordProjectId(projectId!);

    // --- 5. Upload one real contract through the real upload surface.
    await page.goto(`/projects/${projectId}/documents`);
    await expect(page.getByTestId("documents-page")).toBeVisible({ timeout: 30_000 });

    //     The real upload surface: the file input lives inside the upload
    //     dialog, so it must be opened first, and staging a file is separate
    //     from uploading it. A .pdf defaults to the "contract" document type
    //     (defaultDocumentTypeForFile), which is what this journey needs.
    await page.getByRole("button", { name: /upload document/i }).click();
    await expect(page.getByTestId("document-upload-surface")).toBeVisible({ timeout: 15_000 });
    await page.setInputFiles('input[type="file"]', CONTRACT_FIXTURE);

    const uploadButton = page.getByRole("button", { name: /^upload 1 file$/i });
    await expect(uploadButton, "the staged file must be uploadable").toBeEnabled({
      timeout: 15_000,
    });
    await uploadButton.click();

    // --- 6. Wait for the async pipeline to actually LAND.
    //
    //        A 200 from /health is NOT a completion signal: the endpoint answers
    //        200 with single_document_coverage = null while the analysis has not
    //        produced an assessment yet -- which is exactly the state production
    //        was stuck in. Accepting the first 200 made this spec pass or fail on
    //        timing luck. SingleDocumentHealth fetches once with no refetch
    //        interval, so poll the way a waiting user does: reload until the
    //        assessment exists, bounded, then fail loudly if it never does.
    let vector = await loadHealthVector(page, projectId!);
    const analysisDeadline = Date.now() + ANALYSIS_TIMEOUT_MS;
    while (!vector.single_document_coverage && Date.now() < analysisDeadline) {
      await page.waitForTimeout(HEALTH_POLL_INTERVAL_MS);
      vector = await loadHealthVector(page, projectId!);
    }

    // --- 7. /health = 200 with the real single-document payload.
    expect(
      vector.single_document_coverage,
      `single_document_coverage was still null after ${ANALYSIS_TIMEOUT_MS}ms: the async chain ` +
        "did not produce a document assessment -- the exact production failure this gate exists " +
        "to catch",
    ).toBeTruthy();
    const assessments = vector.single_document_coverage?.assessments ?? [];
    expect(assessments).toHaveLength(6);
    expect(new Set(assessments.map((a) => a.category))).toEqual(
      new Set(CANONICAL_CATEGORIES),
    );

    const granularity = vector.single_document_evidence_granularity;
    expect(granularity, "granularity must be disclosed, not inferred").toBeTruthy();

    // INV-1, per assessment and per state. The domain contract
    // (CategoryAssessment._enforce_consistency) is that PRESENT carries
    // qualifying evidence while INSUFFICIENT_EVIDENCE carries NONE and must say
    // what is missing. Granularity is a document-level disclosure of what the
    // ids would identify, so it does NOT imply any category reached PRESENT --
    // a contract where nothing is evidenced is an honest, valid outcome.
    for (const assessment of assessments) {
      const ids = assessment.evidence_clause_ids ?? [];
      const label = `${assessment.category} (${assessment.state})`;

      expect(assessment.evidence_count ?? 0, `${label}: count must match its ids`).toBe(ids.length);
      expect(new Set(ids).size, `${label}: clause ids must not repeat`).toBe(ids.length);

      if (assessment.state === "present") {
        expect(ids.length, `${label}: PRESENT requires qualifying evidence`).toBeGreaterThan(0);
        if (granularity === "clause") {
          for (const id of ids) {
            expect(id, `${label}: clause granularity means persisted clause UUIDs`).toMatch(
              /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/,
            );
          }
        }
      } else {
        expect(ids.length, `${label}: INSUFFICIENT_EVIDENCE must carry no evidence`).toBe(0);
        expect(
          (assessment.missing_data ?? []).length,
          `${label}: INSUFFICIENT_EVIDENCE must state what is missing`,
        ).toBeGreaterThan(0);
        expect(assessment.gap, `${label}: INSUFFICIENT_EVIDENCE requires an actionable gap`)
          .toBeTruthy();
      }
    }

    // --- 8. The user-visible surface. The granularity disclosure and the six
    //        tiles render only on SingleDocumentHealth's success path -- the
    //        loading, error, not-found and unavailable states each render a
    //        different element instead -- so their presence IS the assertion
    //        that the real surface rendered.
    const granularityDisclosure = page.getByTestId("health-granularity");
    await expect(granularityDisclosure).toBeVisible({ timeout: 60_000 });

    for (const category of CANONICAL_CATEGORIES) {
      await expect(
        page.getByTestId(`health-category-${category}`),
        `${category} tile must render`,
      ).toBeVisible();
    }

    // --- 9. Honest null: never 0%, never a fabricated measured score, and an
    //        insufficient tile must say what is missing and what to do -- per
    //        tile, not merely somewhere on the page.
    for (const category of CANONICAL_CATEGORIES) {
      const tile = page.getByTestId(`health-category-${category}`);
      const tileText = await tile.innerText();
      expect(tileText, `${category}: INV-1 -- unknown must never render as 0%`).not.toMatch(
        /\b0\s*%/,
      );

      const isUnknown = tileText.includes("Unknown / Insufficient evidence");
      if (isUnknown) {
        await expect(
          tile.getByTestId("health-missing-data"),
          `${category}: an unknown tile must state what is missing`,
        ).toBeVisible();
        await expect(
          tile.getByTestId("health-gap"),
          `${category}: an unknown tile must offer an action`,
        ).toBeVisible();
      }
    }

    // --- 10. Granularity disclosed in the UI, matching the API's claim.
    const granularityText = await granularityDisclosure.innerText();
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
    //         Scoped to the Health region this journey owns. A page-wide
    //         /finalizing/i scan matched AnalysisProgressTracker's STATIC stage
    //         label ("Finalizing" is one of four names always listed), not a
    //         progress claim -- its live claim is "Currently: <stage>" -- so it
    //         asserted nothing while looking like it did. The tracker also
    //         reopens its SSE stream on reload, after this analysis already
    //         finished, so its live state is not this journey's to assert.
    const healthRegion = page.getByRole("region", { name: "Document health" });
    await expect(healthRegion).toBeVisible();
    await expect(page.getByTestId("health-loading")).toHaveCount(0);
    await expect(page.getByTestId("health-error")).toHaveCount(0);
    await expect(page.getByTestId("health-unavailable")).toHaveCount(0);
    await expect(page.getByTestId("health-not-found")).toHaveCount(0);
    await expect(
      healthRegion.locator(".animate-spin"),
      "the Health surface must not still claim to be working",
    ).toHaveCount(0);

    // --- 13. No console exception attributable to this surface.
    expect(consoleErrors, "no attributable console errors").toEqual([]);
  });
});
