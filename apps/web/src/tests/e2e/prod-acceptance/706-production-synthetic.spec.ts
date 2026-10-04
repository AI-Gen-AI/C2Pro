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
  tenantId: string;
};

type RefreshedApiAuthHeaders = {
  Authorization: string;
  "X-Tenant-ID": string;
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

async function quiesceBrowserPage(page: Page): Promise<void> {
  await page.goto("about:blank");
}

async function createPollingAuthPage(page: Page): Promise<Page> {
  const frontendOrigin = requireProductionOrigin(page.url());
  const expectedOrganizationId =
    process.env.PROD_ACCEPTANCE_CLERK_ORGANIZATION_ID;
  if (!expectedOrganizationId) {
    throw new Error(
      "PROD_ACCEPTANCE_MISSING_ENV:PROD_ACCEPTANCE_CLERK_ORGANIZATION_ID",
    );
  }

  const authPage = await page.context().newPage();
  await authPage.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (url.origin === frontendOrigin && url.pathname.startsWith("/api/")) {
      await route.abort();
      return;
    }
    await route.continue();
  });

  await authPage.goto(`${frontendOrigin}/projects`, {
    waitUntil: "domcontentloaded",
  });
  requireProductionOrigin(authPage.url());

  try {
    await authPage.waitForFunction(
      (expectedOrgId) =>
        window.Clerk?.session?.status === "active" &&
        window.Clerk?.organization?.id === expectedOrgId,
      expectedOrganizationId,
      { timeout: 60_000 },
    );
  } catch {
    throw new Error("PROD_ACCEPTANCE_POLL_AUTH_SESSION_NOT_READY");
  }

  return authPage;
}

async function refreshedApiAuthHeaders(
  authPage: Page,
): Promise<RefreshedApiAuthHeaders> {
  if (!observedApiAuthContext) {
    throw new Error("PROD_ACCEPTANCE_API_AUTH_CONTEXT_MISSING");
  }

  const expectedOrganizationId =
    process.env.PROD_ACCEPTANCE_CLERK_ORGANIZATION_ID;
  if (!expectedOrganizationId) {
    throw new Error(
      "PROD_ACCEPTANCE_MISSING_ENV:PROD_ACCEPTANCE_CLERK_ORGANIZATION_ID",
    );
  }

  const result = await authPage.evaluate(
    async (expectedOrgId) => {
      const session = window.Clerk?.session;
      if (session?.status !== "active") {
        return { state: "SESSION_INACTIVE", token: null };
      }
      if (window.Clerk?.organization?.id !== expectedOrgId) {
        return { state: "WRONG_ORGANIZATION", token: null };
      }
      try {
        const token = await session.getToken({
          organizationId: expectedOrgId,
          skipCache: true,
        });
        return {
          state: token ? "OK" : "TOKEN_NULL",
          token,
        };
      } catch {
        return { state: "TOKEN_ERROR", token: null };
      }
    },
    expectedOrganizationId,
  );

  if (result.state !== "OK" || !result.token) {
    throw new Error(
      `PROD_ACCEPTANCE_POLL_AUTH_REFRESH_FAILED:${result.state}`,
    );
  }

  return {
    Authorization: `Bearer ${result.token}`,
    "X-Tenant-ID": observedApiAuthContext.tenantId,
  };
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

const EVIDENCE_RELOAD_MAX_ATTEMPTS = 3;
const EVIDENCE_RATE_LIMIT_SETTLE_MS = 1_000;

function matchesDocumentDetailApiPath(
  pathname: string,
  documentId: string,
): boolean {
  const paths = [
    `/api/documents/${documentId}`,
    `/api/v1/documents/${documentId}`,
  ];
  return paths.some(
    (expected) => pathname === expected || pathname === `${expected}/`,
  );
}

function positiveHeaderSeconds(value: string | undefined): number | null {
  if (!value) return null;
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

function boundedRateLimitDelayMs(response: Response, header: string): number | null {
  const seconds = positiveHeaderSeconds(response.headers()[header]);
  return seconds === null
    ? null
    : Math.min(seconds * 1_000 + EVIDENCE_RATE_LIMIT_SETTLE_MS, 61_000);
}

function assertEvidenceDocumentResponse(response: Response): void {
  const status = response.status();
  if (status >= 300 && status < 400) {
    throw new Error(`PROD_ACCEPTANCE_EVIDENCE_REDIRECT_REJECTED:${status}`);
  }
  if (status === 401 || status === 403) {
    throw new Error(`PROD_ACCEPTANCE_EVIDENCE_AUTH_FAILED:${status}`);
  }
  if (status >= 400 && status < 500 && status !== 429) {
    throw new Error(`PROD_ACCEPTANCE_EVIDENCE_HTTP_${status}`);
  }
  if (status !== 200 && status !== 429) {
    throw new Error(`PROD_ACCEPTANCE_EVIDENCE_HTTP_${status}`);
  }
}

async function waitForFreshEvidenceReloadWindow(
  page: Page,
  initialDocumentResponse: Response,
): Promise<void> {
  assertEvidenceDocumentResponse(initialDocumentResponse);
  if (initialDocumentResponse.status() !== 200) {
    throw new Error(
      `PROD_ACCEPTANCE_EVIDENCE_INITIAL_DOCUMENT_HTTP_${initialDocumentResponse.status()}`,
    );
  }

  // Evidence is a fan-out UI. Start its hard-refresh proof in the next
  // production fixed-window budget when the server exposes that boundary,
  // rather than racing the same user budget already consumed by processing.
  const resetMs = boundedRateLimitDelayMs(
    initialDocumentResponse,
    "x-ratelimit-reset",
  );
  if (resetMs !== null) {
    await page.waitForTimeout(resetMs);
  }
}

async function reloadExactEvidenceAddress(
  page: Page,
  projectId: string,
  documentId: string,
  clauseId: string,
): Promise<void> {
  const targetUrl =
    `${baseUrl()}/projects/${projectId}/evidence?documentId=${encodeURIComponent(documentId)}&highlightId=${encodeURIComponent(clauseId)}`;

  for (let attempt = 1; attempt <= EVIDENCE_RELOAD_MAX_ATTEMPTS; attempt += 1) {
    const documentResponse = page.waitForResponse(
      (response) =>
        response.request().method() === "GET" &&
        matchesDocumentDetailApiPath(responsePath(response), documentId),
      { timeout: 60_000 },
    );

    if (attempt === 1) {
      await page.reload({ waitUntil: "domcontentloaded" });
    } else {
      await page.goto(targetUrl, { waitUntil: "domcontentloaded" });
    }

    await page.waitForURL(
      (url) =>
        url.pathname === `/projects/${projectId}/evidence` &&
        url.searchParams.get("documentId") === documentId &&
        url.searchParams.get("highlightId") === clauseId,
      { timeout: 30_000 },
    );

    const response = await documentResponse;
    assertEvidenceDocumentResponse(response);
    if (response.status() === 200) return;

    const retryMs = boundedRateLimitDelayMs(response, "retry-after");
    if (retryMs === null) {
      throw new Error("PROD_ACCEPTANCE_EVIDENCE_RETRY_AFTER_MISSING");
    }

    // Stop React Query retries from spending the next fixed window while we
    // honor the server's Retry-After. The next attempt returns to the exact
    // same deep link and must still resolve the same clause.
    await quiesceBrowserPage(page);
    await page.waitForTimeout(retryMs);
  }

  throw new Error("PROD_ACCEPTANCE_EVIDENCE_RATE_LIMIT_TIMEOUT");
}

async function resolveConfiguredProductionBackendOrigin(
  page: Page,
): Promise<string> {
  const runtimeBackendUrlPath = "/api/runtime/backend-url";
  // Vercel can canonicalize c2pro.io <-> www.c2pro.io. Bind this trust
  // anchor to the browser origin actually reached after auth/navigation,
  // then re-validate it against the strict production frontend allowlist.
  const frontendOrigin = requireProductionOrigin(page.url());
  let response: APIResponse;
  try {
    response = await page.request.get(
      `${frontendOrigin}${runtimeBackendUrlPath}`,
      {
        failOnStatusCode: false,
        maxRedirects: 0,
        timeout: 60_000,
      },
    );
  } catch (error) {
    const candidateName = error instanceof Error ? error.name : "";
    const errorName = /^[A-Za-z0-9_.-]+$/.test(candidateName)
      ? candidateName
      : "UnknownError";
    // Do not propagate Playwright transport call logs because the frontend
    // request context can include authenticated session cookies.
    // eslint-disable-next-line preserve-caught-error -- security redaction boundary
    throw new Error(
      `PROD_ACCEPTANCE_BACKEND_ORIGIN_REQUEST_ERROR:${errorName}`,
    );
  }
  if (response.status() !== 200) {
    throw new Error(
      `PROD_ACCEPTANCE_BACKEND_ORIGIN_INVALID:status=${response.status()}`,
    );
  }

  const payload = (await response.json()) as { apiBaseUrl?: unknown };
  if (typeof payload.apiBaseUrl !== "string") {
    throw new Error("PROD_ACCEPTANCE_BACKEND_ORIGIN_INVALID");
  }

  let parsed: URL;
  try {
    parsed = new URL(payload.apiBaseUrl);
  } catch {
    throw new Error("PROD_ACCEPTANCE_BACKEND_ORIGIN_INVALID");
  }
  if (
    parsed.protocol !== "https:" ||
    parsed.username !== "" ||
    parsed.password !== ""
  ) {
    throw new Error("PROD_ACCEPTANCE_BACKEND_ORIGIN_INVALID");
  }
  return parsed.origin;
}

function captureObservedApiAuthContext(
  response: Response,
  configuredBackendOrigin: string,
): void {
  const observedOrigin = new URL(response.url()).origin;
  if (observedOrigin !== configuredBackendOrigin) {
    throw new Error("PROD_ACCEPTANCE_BACKEND_ORIGIN_MISMATCH");
  }

  const requestHeaders = response.request().headers();
  const authorization = requestHeaders.authorization;
  const tenantId = requestHeaders["x-tenant-id"];
  if (!authorization || !tenantId) {
    throw new Error("PROD_ACCEPTANCE_API_AUTH_CONTEXT_MISSING");
  }
  observedApiAuthContext = {
    origin: configuredBackendOrigin,
    tenantId,
  };
}

async function loadDocument(
  page: Page,
  authPage: Page,
  projectId: string,
  documentId: string,
): Promise<{
  status: number;
  record: DocumentRecord | null;
  retryAfterSeconds: number | null;
}> {
  if (!observedApiAuthContext) {
    throw new Error("PROD_ACCEPTANCE_DOCUMENT_AUTH_CONTEXT_MISSING");
  }

  const headers = await refreshedApiAuthHeaders(authPage);
  let response: APIResponse;
  try {
    response = await page.request.get(
      `${observedApiAuthContext.origin}/api/v1/projects/${projectId}/documents`,
      {
        failOnStatusCode: false,
        maxRedirects: 0,
        headers,
        timeout: 60_000,
      },
    );
  } catch (error) {
    const candidateName = error instanceof Error ? error.name : "";
    const errorName = /^[A-Za-z0-9_.-]+$/.test(candidateName)
      ? candidateName
      : "UnknownError";
    // Do not propagate Playwright transport call logs because they can include
    // Authorization/X-Tenant-ID from this direct authenticated request.
    // eslint-disable-next-line preserve-caught-error -- security redaction boundary
    throw new Error(`PROD_ACCEPTANCE_DOCUMENT_REQUEST_ERROR:${errorName}`);
  }

  const status = response.status();
  if (status >= 300 && status < 400) {
    throw new Error(`PROD_ACCEPTANCE_DOCUMENT_REDIRECT_REJECTED:${status}`);
  }
  if (status === 401 || status === 403) {
    throw new Error(`PROD_ACCEPTANCE_DOCUMENT_AUTH_FAILED:${status}`);
  }
  if (status >= 400 && status < 500 && status !== 429) {
    throw new Error(`PROD_ACCEPTANCE_DOCUMENT_HTTP_${status}`);
  }
  if (status === 429) {
    const rawRetryAfter = response.headers()["retry-after"];
    const parsedRetryAfter = rawRetryAfter
      ? Number.parseInt(rawRetryAfter, 10)
      : Number.NaN;
    return {
      status,
      record: null,
      retryAfterSeconds:
        Number.isFinite(parsedRetryAfter) && parsedRetryAfter > 0
          ? parsedRetryAfter
          : null,
    };
  }
  if (status !== 200) {
    return { status, record: null, retryAfterSeconds: null };
  }

  const payload = (await response.json()) as DocumentsPayload | DocumentRecord[];
  const items = Array.isArray(payload) ? payload : (payload.items ?? []);
  const record = items.find((item) => item.id === documentId);
  if (!record) {
    throw new Error(`PROD_ACCEPTANCE_DOCUMENT_NOT_LISTED:${documentId}`);
  }
  return { status, record, retryAfterSeconds: null };
}

const DOCUMENT_TERMINAL_PATTERN =
  /^(analyzed|review_required|failed_retryable|needs_changes|error)$/;
const DOCUMENT_FAILURE_STATES = new Set([
  "failed_retryable",
  "needs_changes",
  "error",
]);
const DOCUMENT_POLL_INTERVAL_MS = 10_000;
const HEALTH_POLL_INTERVAL_MS = 10_000;
const HEALTH_POLL_MAX_REQUESTS = 6;

async function pollDocumentUntilTerminal(
  page: Page,
  authPage: Page,
  projectId: string,
  documentId: string,
): Promise<DocumentRecord> {
  const deadline = Date.now() + PROCESSING_TIMEOUT_MS;
  let latest: DocumentRecord | null = null;
  let lastHttpStatus = 0;

  while (Date.now() < deadline) {
    const observation = await loadDocument(
      page,
      authPage,
      projectId,
      documentId,
    );
    lastHttpStatus = observation.status;
    if (observation.record) {
      latest = observation.record;
      const lifecycle = String(latest.lifecycle_status ?? "").toLowerCase();
      if (DOCUMENT_TERMINAL_PATTERN.test(lifecycle)) {
        return latest;
      }
    }

    const remainingMs = deadline - Date.now();
    if (remainingMs <= 0) break;
    const retryMs =
      observation.status === 429 && observation.retryAfterSeconds
        ? Math.max(
            DOCUMENT_POLL_INTERVAL_MS,
            observation.retryAfterSeconds * 1_000,
          )
        : DOCUMENT_POLL_INTERVAL_MS;
    await page.waitForTimeout(Math.min(retryMs, 60_000, remainingMs));
  }

  throw new Error(
    "PROD_ACCEPTANCE_PROCESSING_TIMEOUT:" +
      `last_http_status=${lastHttpStatus};` +
      `last_lifecycle=${latest?.lifecycle_status ?? "null"};` +
      `last_status=${latest?.status ?? "null"}`,
  );
}

async function waitForDocumentAttentionOrCompletion(
  page: Page,
  authPage: Page,
  projectId: string,
  documentId: string,
): Promise<DocumentRecord> {
  return pollDocumentUntilTerminal(page, authPage, projectId, documentId);
}

async function waitForAnalyzed(
  page: Page,
  authPage: Page,
  projectId: string,
  documentId: string,
): Promise<DocumentRecord> {
  const latest = await pollDocumentUntilTerminal(
    page,
    authPage,
    projectId,
    documentId,
  );
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
  authPage: Page,
  projectId: string,
): Promise<{
  status: number;
  vector: HealthVector | null;
  retryAfterSeconds: number | null;
}> {
  if (!observedApiAuthContext) {
    throw new Error("PROD_ACCEPTANCE_HEALTH_AUTH_CONTEXT_MISSING");
  }

  const headers = await refreshedApiAuthHeaders(authPage);
  let response: APIResponse;
  try {
    response = await page.request.get(
      `${observedApiAuthContext.origin}/api/v1/projects/${projectId}/health`,
      {
        failOnStatusCode: false,
        maxRedirects: 0,
        headers,
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

  if (status >= 300 && status < 400) {
    throw new Error(`PROD_ACCEPTANCE_HEALTH_REDIRECT_REJECTED:${status}`);
  }
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
  authPage: Page,
  projectId: string,
): Promise<HealthVector> {
  let lastStatus = 0;
  let lastVector: HealthVector | null = null;

  for (let attempt = 1; attempt <= HEALTH_POLL_MAX_REQUESTS; attempt += 1) {
    const observation = await loadHealth(page, authPage, projectId);
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

  const configuredBackendOrigin =
    await resolveConfiguredProductionBackendOrigin(page);

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
  captureObservedApiAuthContext(response, configuredBackendOrigin);
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

    observedApiAuthContext = null;
    await signInSyntheticProductionUser(page);

    const projectName = buildSyntheticProjectName();
    const projectId = await createProject(page, projectName);
    const upload = await uploadFixture(page, projectId);
    const pollingAuthPage = await createPollingAuthPage(page);
    await quiesceBrowserPage(page);

    writeRunEvidence({
      run_id: runId,
      project_id: projectId,
      document_id: upload.documentId,
      upload_task_id: upload.taskId,
      hitl_exercised: false,
    });

    let terminal = await waitForDocumentAttentionOrCompletion(
      page,
      pollingAuthPage,
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
      await quiesceBrowserPage(page);
      terminal = await waitForAnalyzed(
        page,
        pollingAuthPage,
        projectId,
        upload.documentId,
      );
    } else if (requireHitl()) {
      throw new Error(
        `PROD_ACCEPTANCE_HITL_REQUIRED_NOT_REACHED:${terminal.lifecycle_status ?? "null"}`,
      );
    }

    expect(terminal.lifecycle_status).toBe("analyzed");

    const health = await waitForHealth(page, pollingAuthPage, projectId);
    const refreshedHealth = page.waitForResponse(
      (response) =>
        response.request().method() === "GET" &&
        response.status() === 200 &&
        matchesProjectApiPath(responsePath(response), projectId, "health"),
      { timeout: 60_000 },
    );
    await page.goto(`${baseUrl()}/projects/${projectId}/analysis`);
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
    const initialEvidenceDocumentResponse = page.waitForResponse(
      (response) =>
        response.request().method() === "GET" &&
        matchesDocumentDetailApiPath(responsePath(response), upload.documentId),
      { timeout: 60_000 },
    );
    await evidenceLink.click();
    await page.waitForURL(
      (url) =>
        url.pathname === `/projects/${projectId}/evidence` &&
        url.searchParams.get("documentId") === upload.documentId &&
        url.searchParams.get("highlightId") === clauseId,
      { timeout: 30_000 },
    );
    const activeEvidence = page.locator(
      '[data-testid="evidence-entity-card"][data-active="true"]',
    );
    const sourceClauseEvidence = page.getByTestId("evidence-link-source-clause");
    const exactEvidenceLanding = activeEvidence.or(sourceClauseEvidence).first();
    await expect(exactEvidenceLanding).toBeVisible({ timeout: 30_000 });
    const initialDocumentResponse = await initialEvidenceDocumentResponse;

    if ((await activeEvidence.count()) > 0) {
      await expect(activeEvidence).toContainText(/Page\s+\d+/);
      await expect(activeEvidence).not.toContainText(/Exact location unavailable/i);
      await expect(activeEvidence).toHaveAttribute("data-entity-id", clauseId);
    } else {
      // Health evidence IDs are authoritative clause IDs. When no semantic
      // sidebar entity represents that clause, Evidence intentionally resolves
      // the source clause itself instead of fabricating an entity card.
      await expect(sourceClauseEvidence).toContainText(/showing source clause/i);
      await expect(sourceClauseEvidence).toContainText(/page\s+\d+/i);
      await expect(page.getByTestId("evidence-link-unavailable")).toHaveCount(0);
      await expect(page.getByTestId("evidence-link-document-fallback")).toHaveCount(0);
    }

    // A hard refresh fans out several authenticated UI reads. Preserve the
    // exact evidence address while respecting the production fixed-window
    // limiter instead of misclassifying a legitimate 429 as missing evidence.
    await waitForFreshEvidenceReloadWindow(page, initialDocumentResponse);
    await reloadExactEvidenceAddress(
      page,
      projectId,
      upload.documentId,
      clauseId,
    );
    await expect(activeEvidence.or(sourceClauseEvidence).first()).toBeVisible({
      timeout: 30_000,
    });
    if ((await activeEvidence.count()) > 0) {
      await expect(activeEvidence).toHaveAttribute("data-entity-id", clauseId);
    } else {
      await expect(sourceClauseEvidence).toContainText(/page\s+\d+/i);
      await expect(page.getByTestId("evidence-link-unavailable")).toHaveCount(0);
      await expect(page.getByTestId("evidence-link-document-fallback")).toHaveCount(0);
    }

    // Real UI sign-out and password sign-in again: no storageState restore.
    await pollingAuthPage.close();
    await signOutThroughUi(page);
    await signInSyntheticProductionUser(page);
    const healthAfterRelogin = await waitForHealth(page, page, projectId);
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
