/**
 * S7 Clerk browser UAT, REAL sign-in → three explicit approvals → sign-out
 * → new context with zero cookies → Clerk sign-in → independent DB API GET.
 *
 * Source documents and approved WBS are TEST-ONLY preseeded. This is NOT a
 * complete S1-S8 live-AI ingestion journey nor an actual human signatory.
 * The S7 approval HTTP requests, both Clerk logins, and DB reads are genuine.
 */
import { readFileSync } from "node:fs";
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
}

async function snapshot(page: Page): Promise<Snapshot> {
  const root = `/api/v1/projects/${fixture.projectId}`;
  const [structured, technical] = await Promise.all([
    call(page, `${root}/structured-wbs/canonical-links`),
    call(page, `${root}/technical-wbs/canonical-links`),
  ]);
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
  return { budget: budget!, schedule: schedule!, technical: technicalLinks[0] };
}

test("S7 one canonical WBS: genuine Clerk approvals, signout and clean-context relogin retain 3 links", async ({
  page, browser,
}) => {
  test.setTimeout(300_000);
  expect(fixture.fixtureMode).toBe("synthetic-source-only");
  expect(fixture.approvalEventsSeeded).toBe(false);
  await establishAuthenticatedSession(page);

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

  const before = await snapshot(page);
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
