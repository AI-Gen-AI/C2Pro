import { existsSync, mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";

import {
  expect,
  test,
  type APIResponse,
  type Page,
  type Response,
} from "@playwright/test";

import {
  buildSyntheticProjectName,
  PROD_ACCEPTANCE_FIXTURE,
  requireProductionOrigin,
} from "./support/prod-preflight";
import {
  signInSyntheticProductionUser,
  signOutThroughUi,
} from "./support/prod-auth.synthetic";

const RUN_OUTPUT = path.join(
  process.cwd(),
  "playwright",
  ".prod-acceptance",
  "run.json",
);
const JOURNEY_TIMEOUT_MS = 15 * 60_000;
const PROCESSING_TIMEOUT_MS = 10 * 60_000;

interface DocumentRecord {
  id: string;
  status?: string | null;
  lifecycle_status?: string | null;
  retryable?: boolean;
  review_count?: number | null;
  review_item_id?: string | null;
}

interface DocumentsPayload {
  items?: DocumentRecord[];
}

interface CategoryAssessment {
  category: string;
  state: string;
  evidence_count?: number;
  evidence_clause_ids?: string[];
  missing_data?: string[];
  gap?: unknown;
}

interface HealthVector {
  single_document_coverage?: {
    document_id?: string | null;
    assessments?: CategoryAssessment[];
  } | null;
  single_document_evidence_granularity?: string | null;
  trusted_score?: number | null;
  projected_score?: number | null;
  projected_delta?: number | null;
  pending_review_count?: number | null;
}

type ObservedApiAuthContext = {
  origin: string;
  headers: {
    Authorization: string;
    "X-Tenant-ID": string;
  };
};

let observedApiAuthContext: ObservedApiAuthContext | null = null;

const CANONICAL_CATEGORIES = new Set([
  "SCOPE",
  "BUDGET",
  "TIME",
  "TECHNICAL",
  "LEGAL",
  "QUALITY",
]);

function baseUrl(): string {
  return requireProductionOrigin(
    process.env.PROD_ACCEPTANCE_BASE_URL ?? "https://c2pro.io",
  );
}

function requireHitl(): boolean {
  const raw = process.env.PROD_ACCEPTANCE_REQUIRE_HITL?.toLowerCase();
  return raw === "1" || raw === "true";
}

function responsePath(response: Response): string {
  return new URL(response.url()).pathname;
}

function matchesProjectApiPath(
  pathname: string,
  projectId: string,
  resource: "documents" | "health",
): boolean {
  const paths = [
    `/api/projects/${projectId}/${resource}`,
    `/api/v1/projects/${projectId}/${resource}`,
  ];
  return paths.some(
    (expected) => pathname === expected || pathname === `${expected}/`,
  );
}

function documentListResponse(response: Response, projectId: string): boolean {
  return (
    response.request().method() === "GET" &&
    response.status() === 200 &&
    matchesProjectApiPath(responsePath(response), projectId, "documents")
  );
}

async function loadDocument(
  page: Page,
  projectId: string,
  documentId: string,
): Promise<DocumentRecord> {
  const responsePromise = page.waitForResponse(
    (response) => documentListResponse(response, projectId),
    { timeout: 60_000 },
  );
  await page.goto(`${baseUrl()}/projects/${projectId}/documents`);
  const response = await responsePromise;
  const requestHeaders = response.request().headers();
  const authorization = requestHeaders.authorization;
  const tenantId = requestHeaders["x-tenant-id"];
  if (authorization && tenantId) {
    observedApiAuthContext = {
      origin: requireProductionOrigin(response.url()),
      headers: {
        Authorization: authorization,
        "X-Tenant-ID": tenantId,
      },
    };
  }
  const payload = (await response.json()) as DocumentsPayload | DocumentRecord[];
  const items = Array.isArray(payload) ? payload : (payload.items ?? []);
  const record = items.find((item) => item.id === documentId);
  if (!record) {
    throw new Error(
      `PROD_ACCEPTANCE_DOCUMENT_NOT_LISTED:${documentId}`,
    );
  }
  return record;
}

const DOCUMENT_TERMINAL_PATTERN =
  /^(analyzed|review_required|failed_retryable|needs_changes|error)$/;
const DOCUMENT_FAILURE_STATES = new Set([
  "failed_retryable",
  "needs_changes",
  "error",
]);
const POLL_INTERVALS_MS = [1_000, 2_000, 5_000];
const HEALTH_POLL_INTERVAL_MS = 10_000;
const HEALTH_POLL_MAX_REQUESTS = 6;

async function pollDocumentUntilTerminal(
  page: Page,
  projectId: string,
  documentId: string,
): Promise<DocumentRecord> {
  let latest = await loadDocument(page, projectId, documentId);

  try {
    await expect
      .poll(
        async () => {
          latest = await loadDocument(page, projectId, documentId);
          return String(latest.lifecycle_status ?? "").toLowerCase();
        },
        {
          timeout: PROCESSING_TIMEOUT_MS,
          intervals: POLL_INTERVALS_MS,
        },
      )
      .toMatch(DOCUMENT_TERMINAL_PATTERN);
  } catch {
    throw new Error(
      `PROD_ACCEPTANCE_PROCESSING_TIMEOUT:last_lifecycle=${latest.lifecycle_status ?? "null"};last_status=${latest.status ?? "null"}`,
    );
  }

  return latest;
}

async function waitForDocumentAttentionOrCompletion(
  page: Page,
  projectId: string,
  documentId: string,
): Promise<DocumentRecord> {
  return pollDocumentUntilTerminal(page, projectId, documentId);
}

async function waitForAnalyzed(
  page: Page,
  projectId: string,
  documentId: string,
): Promise<DocumentRecord> {
  const latest = await pollDocumentUntilTerminal(page, projectId, documentId);
  const lifecycle = String(latest.lifecycle_status ?? "").toLowerCase();
  if (lifecycle === "analyzed") return latest;
  if (DOCUMENT_FAILURE_STATES.has(lifecycle)) {
    throw new Error(
      `PROD_ACCEPTANCE_ANALYSIS_TERMINAL_FAILURE:${lifecycle}`,
    );
  }
  throw new Error(`PROD_ACCEPTANCE_ANALYZED_TIMEOUT:last_lifecycle=${lifecycle}`);
}

async function loadHealth(
  page: Page,
  projectId: string,
): Promise<{
  status: number;
  vector: HealthVector | null;
  retryAfterSeconds: number | null;
}> {
  if (!observedApiAuthContext) {
    throw new Error("PROD_ACCEPTANCE_HEALTH_AUTH_CONTEXT_MISSING");
  }

  let response: APIResponse;
  try {
    response = await page.request.get(
      `${observedApiAuthContext.origin}/api/v1/projects/${projectId}/health`,
      {
        failOnStatusCode: false,
        headers: observedApiAuthContext.headers,
        timeout: 60_000,
      },
    );
  } catch (error) {
    const candidateName = error instanceof Error ? error.name : "";
    const errorName = /^[A-Za-z0-9_.-]+$/.test(candidateName)
      ? candidateName
      : "UnknownError";
    // Intentionally omit the original caught error because Playwright transport
    // call logs can contain Authorization/X-Tenant-ID. This boundary must redact them.
    // eslint-disable-next-line preserve-caught-error -- security redaction boundary
    throw new Error(`PROD_ACCEPTANCE_HEALTH_REQUEST_ERROR:${errorName}`);
  }
  const status = response.status();

  if (status === 401 || status === 403) {
    throw new Error(`PROD_ACCEPTANCE_HEALTH_AUTH_FAILED:${status}`);
  }
  if (status >= 400 && status < 500 && status !== 429) {
    throw new Error(`PROD_ACCEPTANCE_HEALTH_HTTP_${status}`);
  }

  if (status === 429) {
    // Honor Retry-After without exposing any credential or response payload.
    const rawRetryAfter = response.headers()["retry-after"];
    const parsedRetryAfter = rawRetryAfter ? Number.parseInt(rawRetryAfter, 10) : Number.NaN;
    return {
      status,
      vector: null,
      retryAfterSeconds:
        Number.isFinite(parsedRetryAfter) && parsedRetryAfter > 0
          ? parsedRetryAfter
          : null,
    };
  }

  if (status !== 200) {
    return { status, vector: null, retryAfterSeconds: null };
  }

  return {
    status,
    vector: (await response.json()) as HealthVector,
    retryAfterSeconds: null,
  };
}

async function waitForHealth(
  page: Page,
  projectId: string,
): Promise<HealthVector> {
  let lastStatus = 0;
  let lastVector: HealthVector | null = null;

  for (let attempt = 1; attempt <= HEALTH_POLL_MAX_REQUESTS; attempt += 1) {
    const observation = await loadHealth(page, projectId);
    lastStatus = observation.status;
    if (observation.vector) {
      lastVector = observation.vector;
      if (lastVector.single_document_coverage) {
        return lastVector;
      }
    }

    if (attempt === HEALTH_POLL_MAX_REQUESTS) break;

    const retryMs =
      observation.status === 429 && observation.retryAfterSeconds
        ? Math.max(
            HEALTH_POLL_INTERVAL_MS,
            observation.retryAfterSeconds * 1_000,
          )
        : HEALTH_POLL_INTERVAL_MS;
    await page.waitForTimeout(Math.min(retryMs, 60_000));
  }

  const coverage = lastVector?.single_document_coverage ?? null;
  const assessmentCount = coverage?.assessments?.length ?? 0;
  throw new Error(
    "PROD_ACCEPTANCE_HEALTH_TIMEOUT:" +
      `last_status=${lastStatus};` +
      `coverage_document_id=${coverage?.document_id ?? "null"};` +
      `assessment_count=${assessmentCount}`,
  );
}

async function createProject(page: Page, projectName: string): Promise<string> {
  await page.goto(`${baseUrl()}/projects`);
  await page.getByRole("button", { name: /new project|create project/i }).first().click();
  const input = page.getByTestId("project-name-input");
  await expect(input).toBeEditable({ timeout: 20_000 });
  await input.fill(projectName);
  await page.getByRole("button", { name: "Next step" }).click();
  await page.getByRole("button", { name: "Review project" }).click();
  const create = page.getByTestId("create-project-button");
  await expect(create).toBeEnabled({ timeout: 15_000 });
  await create.click();
  await page.waitForURL(/\/projects\/[0-9a-f-]{36}\/documents/, {
    timeout: 60_000,
  });
  const id = page.url().match(/\/projects\/([0-9a-f-]{36})/)?.[1];
  if (!id) throw new Error("PROD_ACCEPTANCE_PROJECT_ID_UNRESOLVED");
  return id;
}

async function uploadFixture(
  page: Page,
  projectId: string,
): Promise<{ documentId: string; taskId: string }> {
  await expect(page.getByTestId("documents-page")).toBeVisible({
    timeout: 30_000,
  });
  await page.getByRole("button", { name: /upload document/i }).click();
  const surface = page.getByTestId("document-upload-surface");
  await expect(surface).toBeVisible({ timeout: 15_000 });
  await page.setInputFiles('input[type="file"]', PROD_ACCEPTANCE_FIXTURE);

  const accepted = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      matchesProjectApiPath(responsePath(response), projectId, "documents"),
    { timeout: 120_000 },
  );
  await page.getByRole("button", { name: /^upload 1 file$/i }).click();
  const response = await accepted;
  if (!response.ok()) {
    throw new Error(`PROD_ACCEPTANCE_UPLOAD_REJECTED:${response.status()}`);
  }
  const payload = (await response.json()) as {
    id?: string;
    document_id?: string;
    task_id?: string | null;
  };
  const documentId = payload.id ?? payload.document_id;
  if (!documentId) throw new Error("PROD_ACCEPTANCE_UPLOAD_NO_DOCUMENT_ID");
  if (!payload.task_id) throw new Error("PROD_ACCEPTANCE_UPLOAD_NOT_ENQUEUED");
  await expect(surface).toBeHidden({ timeout: 60_000 });
  return { documentId, taskId: payload.task_id };
}

async function approveExactDocumentReview(
  page: Page,
  projectId: string,
  reviewItemId: string,
): Promise<void> {
  await page.goto(
    `${baseUrl()}/projects/${projectId}/review?itemId=${encodeURIComponent(reviewItemId)}`,
  );
  const pageRoot = page.getByTestId("review-page");
  await expect(pageRoot).toBeVisible({ timeout: 30_000 });

  const card = page.getByTestId(`review-item-${reviewItemId}`);
  await expect(card).toBeVisible({ timeout: 30_000 });
  const approve = card.getByTestId(`approve-${reviewItemId}`);
  await expect(approve).toBeEnabled({ timeout: 30_000 });
  await approve.click();

  const dialog = page.getByRole("dialog", { name: /approve review item/i });
  await expect(dialog).toBeVisible();
  await dialog.getByRole("button", { name: /confirm approve/i }).click();
  await expect(dialog).toBeHidden({ timeout: 120_000 });
}

function writeRunEvidence(value: Record<string, unknown>): void {
  const directory = path.dirname(RUN_OUTPUT);
  if (!existsSync(directory)) mkdirSync(directory, { recursive: true });
  writeFileSync(RUN_OUTPUT, JSON.stringify(value, null, 2), "utf8");
}

test.describe("Issue #706 production synthetic acceptance", () => {
  test.describe.configure({ mode: "serial", timeout: JOURNEY_TIMEOUT_MS });

  test("real user completes the canonical production journey", async ({ page }) => {
    const runId = process.env.PROD_ACCEPTANCE_RUN_ID;
    if (!runId) throw new Error("PROD_ACCEPTANCE_MISSING_ENV:PROD_ACCEPTANCE_RUN_ID");

    await signInSyntheticProductionUser(page);

    const projectName = buildSyntheticProjectName();
    const projectId = await createProject(page, projectName);
    const upload = await uploadFixture(page, projectId);

    writeRunEvidence({
      run_id: runId,
      project_id: projectId,
      document_id: upload.documentId,
      upload_task_id: upload.taskId,
      hitl_exercised: false,
    });

    let terminal = await waitForDocumentAttentionOrCompletion(
      page,
      projectId,
      upload.documentId,
    );

    let hitlExercised = false;
    let exercisedReviewItemId: string | null = null;
    if (terminal.lifecycle_status === "review_required") {
      if ((terminal.review_count ?? 0) !== 1 || !terminal.review_item_id) {
        throw new Error(
          "PROD_ACCEPTANCE_REVIEW_NOT_EXACTLY_ADDRESSABLE",
        );
      }
      exercisedReviewItemId = terminal.review_item_id;
      await approveExactDocumentReview(
        page,
        projectId,
        exercisedReviewItemId,
      );
      hitlExercised = true;
      terminal = await waitForAnalyzed(page, projectId, upload.documentId);
    } else if (requireHitl()) {
      throw new Error(
        `PROD_ACCEPTANCE_HITL_REQUIRED_NOT_REACHED:${terminal.lifecycle_status ?? "null"}`,
      );
    }

    expect(terminal.lifecycle_status).toBe("analyzed");

    const health = await waitForHealth(page, projectId);
    const refreshedHealth = page.waitForResponse(
      (response) =>
        response.request().method() === "GET" &&
        response.status() === 200 &&
        matchesProjectApiPath(responsePath(response), projectId, "health"),
      { timeout: 60_000 },
    );
    if (!observedApiAuthContext) {
      throw new Error("PROD_ACCEPTANCE_HEALTH_AUTH_CONTEXT_MISSING");
    }
    await page.goto(
      `${observedApiAuthContext.origin}/projects/${projectId}/analysis`,
    );
    await refreshedHealth;
    const assessments = health.single_document_coverage?.assessments ?? [];
    expect(assessments).toHaveLength(6);
    expect(new Set(assessments.map((item) => item.category))).toEqual(
      CANONICAL_CATEGORIES,
    );

    const healthRegion = page.getByRole("region", { name: "Document health" });
    await expect(healthRegion).toBeVisible();
    await expect(page.getByTestId("health-loading")).toHaveCount(0);
    await expect(page.getByTestId("health-error")).toHaveCount(0);
    await expect(page.getByTestId("health-unavailable")).toHaveCount(0);

    const granularity = health.single_document_evidence_granularity;
    expect(granularity, "Health must disclose evidence granularity").toBeTruthy();
    const granularityText = await page.getByTestId("health-granularity").innerText();
    if (granularity === "clause") expect(granularityText).toMatch(/clause-level/i);
    if (granularity === "document") expect(granularityText).toMatch(/whole-document/i);

    for (const assessment of assessments) {
      const tile = page.getByTestId(`health-category-${assessment.category}`);
      await expect(tile).toBeVisible();
      const ids = assessment.evidence_clause_ids ?? [];
      expect(assessment.evidence_count ?? 0).toBe(ids.length);
      expect(new Set(ids).size).toBe(ids.length);

      if (assessment.state === "present") {
        expect(ids.length, `${assessment.category}: PRESENT needs evidence`).toBeGreaterThan(0);
        await expect(tile.getByTestId("health-state")).toHaveText(/evidence found/i);
        await expect(tile.getByTestId("health-state")).toHaveClass(/emerald/);
      } else {
        expect(ids).toHaveLength(0);
        expect(
          (assessment.missing_data ?? []).length,
          `${assessment.category}: UNKNOWN must say what is missing`,
        ).toBeGreaterThan(0);
        expect(assessment.gap, `${assessment.category}: UNKNOWN needs an action`).toBeTruthy();
        await expect(tile.getByTestId("health-state")).toHaveText(
          /unknown \/ insufficient evidence/i,
        );
        await expect(tile.getByTestId("health-state")).toHaveClass(/amber/);
        await expect(tile.getByTestId("health-state")).not.toHaveClass(/emerald/);
        await expect(tile.getByTestId("health-missing-data")).toBeVisible();
        await expect(tile.getByTestId("health-gap")).toBeVisible();
        expect(await tile.innerText()).not.toMatch(/\b0\s*%/);
      }
    }

    // This synthetic project contains exactly one document. Relational Coherence
    // may not manufacture a headline score before enough reconcilable evidence exists.
    await expect(page.getByTestId("health-coherence-note")).toBeVisible();
    await expect(page.getByTestId("analysis-coherence-score")).toHaveCount(0);

    const evidenceLinks = healthRegion.getByTestId("health-evidence-link");
    expect(
      await evidenceLinks.count(),
      "production qualification fixture must expose clause-level evidence",
    ).toBeGreaterThan(0);

    const evidenceLink = evidenceLinks.first();
    const clauseId = await evidenceLink.getAttribute("data-clause-id");
    if (!clauseId) throw new Error("PROD_ACCEPTANCE_EVIDENCE_CLAUSE_ID_MISSING");
    await evidenceLink.click();
    await page.waitForURL(
      (url) =>
        url.pathname === `/projects/${projectId}/evidence` &&
        url.searchParams.get("highlightId") === clauseId,
      { timeout: 30_000 },
    );
    const activeEvidence = page.locator(
      '[data-testid="evidence-entity-card"][data-active="true"]',
    );
    await expect(activeEvidence).toBeVisible({ timeout: 30_000 });
    await expect(activeEvidence).toContainText(/Page\s+\d+/);
    await expect(activeEvidence).not.toContainText(/Exact location unavailable/i);

    // Hard refresh must preserve the exact evidence address.
    await page.reload();
    await expect(activeEvidence).toBeVisible({ timeout: 30_000 });
    await expect(activeEvidence).toHaveAttribute("data-entity-id", clauseId);

    // Real UI sign-out and password sign-in again: no storageState restore.
    await signOutThroughUi(page);
    await signInSyntheticProductionUser(page);
    const healthAfterRelogin = await waitForHealth(page, projectId);
    expect(
      healthAfterRelogin.single_document_coverage?.assessments?.map(
        (item) => item.category,
      ),
    ).toEqual(expect.arrayContaining([...CANONICAL_CATEGORIES]));

    writeRunEvidence({
      run_id: runId,
      project_id: projectId,
      document_id: upload.documentId,
      upload_task_id: upload.taskId,
      health: {
        granularity,
        assessments: assessments.map((assessment) => ({
          category: assessment.category,
          state: assessment.state,
          evidence_count: assessment.evidence_clause_ids?.length ?? 0,
          missing_data_count: assessment.missing_data?.length ?? 0,
          actionable_gap: Boolean(assessment.gap),
        })),
        coherence_available: false,
      },
      evidence_clause_id: clauseId,
      review_item_id: exercisedReviewItemId,
      hitl_exercised: hitlExercised,
      relogin_verified: true,
    });
  });
});
