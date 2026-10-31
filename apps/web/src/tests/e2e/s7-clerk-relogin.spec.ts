/**
 * S7 Clerk browser UAT, REAL sign-in → three explicit approvals → sign-out
 * → new context with zero cookies → Clerk sign-in → independent DB API GET.
 *
 * Source documents and approved WBS are TEST-ONLY preseeded. This is NOT a
 * complete S1-S8 live-AI ingestion journey nor an actual human signatory.
 * The S7 approval HTTP requests, both Clerk logins, and DB reads are genuine.
 */
import { readFileSync } from "node:fs";

import { approveWithHttpResponse } from "../support/p0b-hitl-http-retry";
import path from "node:path";

import { expect, test, type Page } from "@playwright/test";

import { establishAuthenticatedSession } from "./support/p0b-auth";

interface InputDocument {
  documentId: string;
  revisionId: string;
  blobHash: string;
  sourceLocator: string;
}

interface Fixture {
  projectId: string;
  baselineId: string;
  nodeId: string;
  fixtureMode: "synthetic-source-only";
  approvalEventsSeeded: false;
  budget: InputDocument;
  schedule: InputDocument;
  technical: { documentId: string; revisionId: string; clauseId: string; blobHash: string };
}

const SOURCE = path.join(process.cwd(), "playwright-report", "s7-clerk-source.json");
const CONTRACT = path.join(process.cwd(), "src/tests/e2e/test-data/sample-contract.pdf");
const ANALYSIS_BUDGET_MS = 240_000;
const fixture = JSON.parse(readFileSync(SOURCE, "utf8")) as Fixture;

async function call(
  page: Page,
  url: string,
  method: "GET" | "POST" = "GET",
  body?: Record<string, unknown>,
): Promise<{ status: number; data: unknown }> {
  return page.evaluate(async ({ target, verb, payload }) => {
    // Only the page holding the authentic active Clerk session reads its JWT.
    // The token is never returned to Node, logged, or stored in Playwright evidence.
    const token = await window.Clerk?.session?.getToken();
    if (!token) throw new Error("S7_CLERK_SESSION_TOKEN_MISSING");
    const response = await fetch(target, {
      method: verb,
      headers: {
        Authorization: `Bearer ${token}`,
        ...(payload ? { "Content-Type": "application/json" } : {}),
      },
      ...(payload ? { body: JSON.stringify(payload) } : {}),
    });
    const data: unknown = await response.json().catch(() => null);
    return { status: response.status, data };
  }, { target: url, verb: method, payload: body });
}

type Link = Record<string, unknown>;
interface Snapshot {
  budget: Link;
  schedule: Link;
  technical: Link;
  health: {
    computedAt: string;
    compositeScore: number | null;
    compositeBand: string;
    assessments: Array<{ category: string; state: string }>;
  };
  coherence: {
    globalScore: number | null;
    scoreVersion: string | null;
    scoreReason: string | null;
    missingDimensions: string[];
    categoryScores: Record<string, number | null>;
    evaluatedAt: string;
  };
}

async function snapshot(page: Page): Promise<Snapshot> {
  const root = `/api/v1/projects/${fixture.projectId}`;
  const [structured, technical, health, dashboard] = await Promise.all([
    call(page, `${root}/structured-wbs/canonical-links`),
    call(page, `${root}/technical-wbs/canonical-links`),
    call(page, `${root}/health`),
    call(page, `/api/v1/coherence/dashboard/${fixture.projectId}`),
  ]);
  expect(health.status, "authenticated project Health read").toBe(200);
  expect(dashboard.status, "authenticated persisted Coherence dashboard read").toBe(200);
  expect(structured.status, "Clerk-authenticated structured WBS GET").toBe(200);
  expect(technical.status, "Clerk-authenticated technical WBS GET").toBe(200);
  const structuredLinks = structured.data as Link[];
  const technicalLinks = technical.data as Link[];
  expect(structuredLinks).toHaveLength(2);
  expect(technicalLinks).toHaveLength(1);
  const budget = structuredLinks.find((r) => r.family === "budget");
  const schedule = structuredLinks.find((r) => r.family === "schedule");
  expect(budget, "approved Budget source link").toBeTruthy();
  expect(schedule, "approved Schedule source link").toBeTruthy();
  const triple = [budget!, schedule!, technicalLinks[0]];
  for (const link of triple) {
    expect(link.state).toBe("CURRENT");
    expect(link.wbs_baseline_id).toBe(fixture.baselineId);
    expect(link.wbs_node_id).toBe(fixture.nodeId);
    expect(link.authority).toBe("EXPLICIT_HUMAN_CANONICAL_LINK");
  }
  expect(budget?.source_document_id).toBe(fixture.budget.documentId);
  expect(schedule?.source_document_id).toBe(fixture.schedule.documentId);
  expect(technicalLinks[0]?.technical_document_id).toBe(fixture.technical.documentId);
  const healthBody = health.data as {
    project_id?: string;
    computed_at?: string;
    composite_score?: number | null;
    composite_band?: string;
    single_document_coverage?: { assessments?: Array<{ category: string; state: string }> } | null;
  };
  const scoreBody = dashboard.data as {
    project_id?: string;
    global_score?: number | null;
    score_version?: string | null;
    score_reason?: string | null;
    score_missing_dimensions?: string[] | null;
    sub_scores?: Record<string, number | null>;
    last_updated?: string;
  };
  expect(healthBody.project_id).toBe(fixture.projectId);
  expect(scoreBody.project_id).toBe(fixture.projectId);
  const assessments = healthBody.single_document_coverage?.assessments ?? [];
  expect(assessments, "six real Health assessments, not the no-snapshot fallback").toHaveLength(6);
  expect(new Set(assessments.map((a) => a.category)).size).toBe(6);
  expect(
    scoreBody.global_score !== null && scoreBody.global_score !== undefined ||
      Boolean(scoreBody.score_reason && scoreBody.score_missing_dimensions?.length),
    "evaluated Coherence must be persisted; two empty/null dashboard reads do not prove persistence",
  ).toBe(true);
  expect(Object.keys(scoreBody.sub_scores ?? {})).toHaveLength(6);
  expect(scoreBody.last_updated, "persisted evaluation timestamp").toBeTruthy();

  return {
    budget: budget!, schedule: schedule!, technical: technicalLinks[0],
    health: {
      computedAt: healthBody.computed_at ?? "",
      compositeScore: healthBody.composite_score ?? null,
      compositeBand: healthBody.composite_band ?? "",
      assessments: assessments.map((a) => ({ category: a.category, state: a.state }))
        .sort((a, b) => a.category.localeCompare(b.category)),
    },
    coherence: {
      globalScore: scoreBody.global_score ?? null,
      scoreVersion: scoreBody.score_version ?? null,
      scoreReason: scoreBody.score_reason ?? null,
      missingDimensions: [...(scoreBody.score_missing_dimensions ?? [])].sort(),
      categoryScores: Object.fromEntries(
        Object.entries(scoreBody.sub_scores ?? {}).sort(([a], [b]) => a.localeCompare(b)),
      ),
      evaluatedAt: scoreBody.last_updated ?? "",
    },
  };
}

/** Run the existing P0b graph in the SAME WBS project, rather than fabricating Health rows. */
async function produceRealHealth(page: Page): Promise<void> {
  const projectId = fixture.projectId;
  const deadline = Date.now() + ANALYSIS_BUDGET_MS;
  await page.goto(`/projects/${projectId}/documents`);
  await expect(page.getByTestId("documents-page")).toBeVisible({ timeout: 30_000 });
  await page.getByRole("button", { name: /upload document/i }).click();
  await expect(page.getByTestId("document-upload-surface")).toBeVisible();
  await page.setInputFiles('input[type="file"]', CONTRACT);
  const uploadButton = page.getByRole("button", { name: /^upload 1 file$/i });
  await expect(uploadButton).toBeEnabled();
  const accepted = page.waitForResponse((response) => (
    response.request().method() === "POST" &&
    (["/api/projects/", "/api/v1/projects/"].some(
      (prefix) => new URL(response.url()).pathname.replace(/\\/$/, "") === `${prefix}${projectId}/documents`
    ))
  ), { timeout: 90_000 });
  await uploadButton.click();
  const answer = await accepted;
  expect(answer.ok(), "real contract upload must enqueue analysis").toBe(true);
  const uploaded = await answer.json() as { id?: string; document_id?: string; task_id?: string };
  const documentId = uploaded.id ?? uploaded.document_id;
  expect(documentId).toMatch(/^[0-9a-f-]{36}$/);
  expect(uploaded.task_id, "real Celery analysis must be enqueued").toBeTruthy();
  await expect(page.getByTestId("document-upload-surface")).toBeHidden({ timeout: 60_000 });

  let reviewItemId: string | null = null;
  for (;;) {
    expect(Date.now(), "real analysis did not reach a HITL review").toBeLessThan(deadline);
    const docs = await call(page, `/api/v1/projects/${projectId}/documents`);
    expect(docs.status, "same-project authenticated document read").toBe(200);
    const data = docs.data as { items?: Array<Record<string, unknown>> } | Array<Record<string, unknown>>;
    const items = Array.isArray(data) ? data : data.items ?? [];
    const document = items.find((item) => item.id === documentId);
    const state = String(document?.lifecycle_status ?? "");
    if (state === "review_required") {
      expect(document?.review_count).toBe(1);
      reviewItemId = String(document?.review_item_id ?? "");
      expect(reviewItemId).toBeTruthy();
      break;
    }
    if (["analyzed", "error", "failed_retryable", "needs_changes"].includes(state)) {
      throw new Error(`S7_HEALTH_REAL_GRAPH_HITL_BYPASS_OR_FAILURE:${state}`);
    }
    await page.waitForTimeout(3_000);
  }
  const item = reviewItemId!;
  const queue = await call(page, `/api/v1/hitl/queue?project_id=${projectId}&limit=100`);
  expect(queue.status).toBe(200);
  const rows = (queue.data as { items?: Array<{ item_id: string; row_id?: string }> }).items ?? [];
  const matches = rows.filter((row) => row.item_id === item && row.row_id);
  expect(matches, "exact immutable review row for this new contract").toHaveLength(1);
  const rowId = matches[0].row_id!;
  await page.goto(`/projects/${projectId}/review?itemId=${encodeURIComponent(item)}`);
  const card = page.getByTestId(`review-item-${item}`);
  await expect(card).toBeVisible({ timeout: 30_000 });
  await card.getByTestId(`approve-${item}`).click();
  const dialog = page.getByRole("dialog", { name: /approve review item/i });
  await expect(dialog).toBeVisible();
  const confirm = dialog.getByRole("button", { name: /confirm approve/i });
  await approveWithHttpResponse({
    now: () => Date.now(),
    submitOnce: async (id, remaining) => {
      const [response] = await Promise.all([
        page.waitForResponse((candidate) => candidate.request().method() === "POST" &&
          new URL(candidate.url()).pathname.replace(/\\/$/, "") ===
          `/api/hitl/queue/${encodeURIComponent(id)}/approve`,
        { timeout: remaining }),
        confirm.click({ timeout: remaining }),
      ]);
      return response;
    },
    waitUntilReady: async (remaining) => {
      await expect(confirm).toBeEnabled({ timeout: remaining });
    },
    delay: (ms) => page.waitForTimeout(ms),
    confirmed: async (remaining) => {
      await expect(dialog).toBeHidden({ timeout: remaining });
    },
  }, item, rowId, deadline);

  for (;;) {
    expect(Date.now(), "real graph did not persist analyzed document").toBeLessThan(deadline);
    const docs = await call(page, `/api/v1/projects/${projectId}/documents`);
    expect(docs.status).toBe(200);
    const data = docs.data as { items?: Array<Record<string, unknown>> } | Array<Record<string, unknown>>;
    const items = Array.isArray(data) ? data : data.items ?? [];
    const state = String(items.find((d) => d.id === documentId)?.lifecycle_status ?? "");
    if (state === "analyzed") break;
    if (["error", "failed_retryable", "needs_changes"].includes(state)) {
      throw new Error(`S7_REAL_CONTRACT_ANALYSIS_FAILED:${state}`);
    }
    await page.waitForTimeout(3_000);
  }

  // Completion is the persisted read model, NOT an HTTP-200 or a forged event.
  for (;;) {
    expect(Date.now(), "graph.completed did not yield six persisted Health assessments").toBeLessThan(deadline);
    const response = await call(page, `/api/v1/projects/${projectId}/health`);
    expect(response.status).toBe(200);
    const health = response.data as {
      single_document_coverage?: { assessments?: Array<{ category: string }> } | null;
    };
    const assessments = health.single_document_coverage?.assessments ?? [];
    if (assessments.length === 6) {
      expect(new Set(assessments.map((a) => a.category)).size).toBe(6);
      break;
    }
    await page.waitForTimeout(3_000);
  }
}

test("S7 one canonical WBS: genuine Clerk approvals, signout and clean-context relogin retain 3 links", async ({
  page, browser,
}) => {
  test.setTimeout(600_000);
  expect(fixture.fixtureMode).toBe("synthetic-source-only");
  expect(fixture.approvalEventsSeeded).toBe(false);
  await establishAuthenticatedSession(page);

  // P0b original contract goes through real worker, HITL, graph and snapshot in this exact S7 project.
  await produceRealHealth(page);

  const userBefore = await page.evaluate(() => window.Clerk?.user?.id ?? null);
  expect(userBefore).toBeTruthy();
  const root = `/api/v1/projects/${fixture.projectId}`;
  const review = await call(page, `${root}/technical-wbs/reviews`, "POST", {
    clause_id: fixture.technical.clauseId,
    expected_revision_id: fixture.technical.revisionId,
    expected_blob_hash: fixture.technical.blobHash,
    expected_wbs_baseline_id: fixture.baselineId,
    proposed_wbs_node_id: fixture.nodeId,
    decision: "CONFIRMED_FOR_REVIEW",
    idempotency_key: "s7-clerk-browser-technical-audit",
    reason: "Clerk-authenticated test reviewer confirms immutable technical requirement",
  });
  expect(review.status, JSON.stringify(review.data).slice(0, 200)).toBe(201);
  const audit = review.data as { event_id: string };
  expect(audit.event_id).toBeTruthy();

  const technical = await call(page, `${root}/technical-wbs/canonical-links`, "POST", {
    review_event_id: audit.event_id,
    expected_wbs_baseline_id: fixture.baselineId,
    expected_wbs_node_id: fixture.nodeId,
    approval: "APPROVE_CANONICAL_LINK",
    idempotency_key: "s7-clerk-browser-technical-approval",
    reason: "Explicit synthetic reviewer confirmation of technical-to-WBS relation",
  });
  expect(technical.status, JSON.stringify(technical.data).slice(0, 200)).toBe(201);

  for (const family of ["budget", "schedule"] as const) {
    const source = fixture[family];
    const approved = await call(page, `${root}/structured-wbs/canonical-links`, "POST", {
      family,
      source_document_id: source.documentId,
      source_revision_id: source.revisionId,
      expected_blob_hash: source.blobHash,
      source_locator: source.sourceLocator,
      expected_wbs_baseline_id: fixture.baselineId,
      expected_wbs_node_id: fixture.nodeId,
      approval: "APPROVE_CANONICAL_LINK",
      idempotency_key: `s7-clerk-browser-${family}-approval`,
      reason: `Clerk-authenticated synthetic reviewer confirms ${family} source row`,
    });
    expect(approved.status, JSON.stringify(approved.data).slice(0, 200)).toBe(201);
  }

  // Exactly one genuine evaluation on the SAME three-source/WBS project.
  // No POST, re-score, refresh-trigger or state mutation is allowed after this point.
  const evaluation = await call(page, "/api/v1/coherence/evaluate", "POST", {
    project_id: fixture.projectId,
    low_budget_mode: true,
    include_rag_similarity: false,
  });
  expect(evaluation.status, "same-project Coherence evaluation must complete").toBe(200);
  const evaluated = evaluation.data as {
    overall_score?: number | null;
    score_reason?: string | null;
    score_missing_dimensions?: string[] | null;
  };
  expect(
    evaluated.overall_score !== null && evaluated.overall_score !== undefined ||
      Boolean(evaluated.score_reason && evaluated.score_missing_dimensions?.length),
    "evaluation must produce evidence-backed score or explicit honest null with missing dimensions",
  ).toBe(true);

  const before = await snapshot(page);
  expect(before.coherence.globalScore, "stored Score agrees with the evaluation").toBe(evaluated.overall_score ?? null);
  expect(before.coherence.scoreReason, "stored Score reason agrees with the evaluation").toBe(evaluated.score_reason ?? null);
  await page.getByRole("button", { name: "User menu" }).click();
  await page.getByRole("menuitem", { name: /sign out/i }).click();
  await expect(page).toHaveURL(/\/sign-in/, { timeout: 30_000 });
  await page.waitForFunction(() => window.Clerk?.loaded === true, undefined, { timeout: 30_000 });
  expect(await page.evaluate(() => Boolean(window.Clerk?.session))).toBe(false);
  await page.goto(`/projects/${fixture.projectId}/documents`);
  await expect(page).toHaveURL(/\/sign-in/, { timeout: 30_000 });

  // Explicitly no cookies, local storage or saved auth state in the second browser.
  const fresh = await browser.newContext({
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3100",
    storageState: { cookies: [], origins: [] },
  });
  try {
    const again = await fresh.newPage();
    await establishAuthenticatedSession(again);
    const userAfter = await again.evaluate(() => window.Clerk?.user?.id ?? null);
    expect(userAfter).toBe(userBefore);
    const after = await snapshot(again);
    expect(after, "three exact durable approval receipts after real Clerk relogin").toEqual(before);
  } finally {
    await fresh.close();
  }
});
