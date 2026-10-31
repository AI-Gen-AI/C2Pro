/**
 * PJ-01 steps 16–20 (ACC-01 S8): sign out of Clerk, sign in again as the SAME user in a brand-new browser
 * context, and find everything the journey produced exactly where it was left.
 *
 * "Again" means a new login, not a restored session: the new context starts with an empty storage state
 * (no cookies, no local storage), so nothing of the first session can carry the user over, and the sign-in
 * is the same documented Clerk bootstrap the journey's first step uses (`signInAsJourneyUser`: the Clerk
 * testing sign-in-token flow; no password form or inbox is involved, and that is stated in the evidence).
 * The first session is ended through the application's own "Sign out" control, and the run proves that it
 * is really over (no Clerk session in the page, a protected route sends the browser to sign-in).
 *
 * What must be the same after the new login is read from the application's own API with the new session and
 * compared with what the first session read before leaving: the project, the documents, the revisions and
 * their trust states, the persisted alerts, and the human decisions (who approved which review, when).
 * The Current State report must still rest on revision B. Tokens, cookies and Clerk identifiers other than
 * the "same user" boolean are never recorded.
 */
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";

import { expect, type Page } from "@playwright/test";

import { contractBPdfPath, loadContractBManifest } from "../../../pj01/revision-fixture";
import { assertCurrentStateThroughNavigation } from "./current-state";
import type { Pj01FirstHalfResult, Pj01SecondHalfResult } from "./journey";
import type { Pj01RunRecorder } from "./run-recorder";
import { signInAsJourneyUser } from "./session";

const sha256 = (file: string): string => createHash("sha256").update(readFileSync(file)).digest("hex");

export interface PersistedStateSnapshot {
  project: { id: string; name: string };
  documents: Array<{ id: string; filename: string; documentType: string | null; lifecycleStatus: string }>;
  revisions: Array<{ revNo: number | null; revisionId: string; trustState: string | null; isCurrent: boolean }>;
  alerts: Array<{ id: string; ruleCode: string; status: string }>;
  decisions: Array<{ itemId: string; rowId: string | null; status: string; approvedBy: string | null; approvedAt: string | null }>;
}

interface ApiAnswer {
  status: number;
  body: unknown;
}

/** One authenticated GET with THIS page's own Clerk session (the token never leaves the callback). */
async function get(page: Page, url: string): Promise<ApiAnswer> {
  return page.evaluate(async (target) => {
    const token = await window.Clerk?.session?.getToken();
    if (!token) throw new Error("RELOGIN_AUTH_CONTEXT_MISSING");
    const response = await fetch(target, { headers: { Authorization: `Bearer ${token}` } });
    const text = await response.text();
    let body: unknown = text;
    try {
      body = JSON.parse(text);
    } catch {
      /* keep the text */
    }
    return { status: response.status, body };
  }, url);
}

function itemsOf(body: unknown): Array<Record<string, unknown>> {
  if (Array.isArray(body)) return body as Array<Record<string, unknown>>;
  const items = (body as { items?: unknown } | null)?.items;
  return Array.isArray(items) ? (items as Array<Record<string, unknown>>) : [];
}

const text = (value: unknown): string => (typeof value === "string" ? value : "");
const textOrNull = (value: unknown): string | null => (typeof value === "string" ? value : null);

/** What the application holds for the journey's project, as this session sees it. */
export async function readPersistedState(
  page: Page,
  options: { projectId: string; documentId: string },
): Promise<PersistedStateSnapshot> {
  const { projectId, documentId } = options;
  const [project, documents, revisions, alerts, decisions] = await Promise.all([
    get(page, `/api/v1/projects/${projectId}`),
    get(page, `/api/v1/projects/${projectId}/documents`),
    get(page, `/api/v1/documents/${documentId}/revisions`),
    get(page, `/api/v1/alerts/projects/${projectId}`),
    get(page, `/api/v1/hitl/queue?project_id=${projectId}&limit=100`),
  ]);
  for (const [name, answer] of Object.entries({ project, documents, revisions, alerts, decisions })) {
    expect(answer.status, `${name} must be readable after the session change: ${JSON.stringify(answer.body).slice(0, 200)}`).toBe(200);
  }
  const projectBody = project.body as { id?: string; name?: string };
  return {
    project: { id: text(projectBody.id), name: text(projectBody.name) },
    documents: itemsOf(documents.body)
      .map((d) => ({
        id: text(d.id),
        filename: text(d.filename),
        documentType: textOrNull(d.document_type),
        lifecycleStatus: text(d.lifecycle_status),
      }))
      .sort((a, b) => a.id.localeCompare(b.id)),
    revisions: itemsOf(revisions.body)
      .map((r) => ({
        revNo: typeof r.rev_no === "number" ? r.rev_no : null,
        revisionId: text(r.revision_id),
        trustState: textOrNull(r.trust_state),
        isCurrent: r.is_current === true,
      }))
      .sort((a, b) => (a.revNo ?? 0) - (b.revNo ?? 0) || a.revisionId.localeCompare(b.revisionId)),
    alerts: itemsOf(alerts.body)
      .map((a) => ({ id: text(a.id), ruleCode: text(a.rule_code), status: text(a.status) }))
      .sort((a, b) => a.id.localeCompare(b.id)),
    decisions: itemsOf(decisions.body)
      .map((d) => ({
        itemId: text(d.item_id),
        rowId: textOrNull(d.row_id),
        status: text(d.current_status),
        approvedBy: textOrNull(d.approved_by),
        approvedAt: textOrNull(d.approved_at),
      }))
      .sort((a, b) => (a.rowId ?? "").localeCompare(b.rowId ?? "")),
  };
}

async function clerkUserId(page: Page): Promise<string | null> {
  return page.evaluate(() => window.Clerk?.user?.id ?? null);
}

export interface Pj01ReloginResult {
  before: PersistedStateSnapshot;
  after: PersistedStateSnapshot;
}

export async function runPj01Relogin(
  page: Page,
  options: {
    baseURL: string;
    recorder: Pj01RunRecorder;
    first: Pj01FirstHalfResult;
    second: Pj01SecondHalfResult;
  },
): Promise<Pj01ReloginResult> {
  const { baseURL, recorder, first, second } = options;
  const { projectId, documentId } = first;

  const before = await recorder.step("PJ01-S16", "Persisted state before leaving (project, documents, revisions, alerts, decisions)", async () => {
    const snapshot = await readPersistedState(page, { projectId, documentId });
    // The journey really left something to find again: two revisions, a trusted B, and human decisions.
    expect(snapshot.revisions.length, "revisions A and B exist").toBeGreaterThanOrEqual(2);
    expect(
      snapshot.revisions.some((revision) => revision.revisionId === second.whatChanged.targetRevisionId && revision.trustState === "trusted"),
      "revision B is trusted before the sign-out",
    ).toBe(true);
    // The review queue lists one row per document (revisions A and B share the document's item id), so the
    // count of named approvals is at least one; which approval belongs to B is proven by the PostgreSQL trace.
    expect(snapshot.decisions.filter((d) => d.status.toUpperCase() === "APPROVED" && d.approvedBy).length, "a named human approval").toBeGreaterThanOrEqual(1);
    recorder.record("relogin.before", {
      documents: snapshot.documents.length,
      revisions: snapshot.revisions.length,
      alerts: snapshot.alerts.length,
      decisions: snapshot.decisions.length,
    });
    return snapshot;
  });

  const userBefore = await clerkUserId(page);
  expect(userBefore, "a signed-in Clerk user before leaving").toBeTruthy();

  await recorder.step("PJ01-S17", "Sign out through the user menu; the session is really over", async () => {
    await page.getByRole("button", { name: "User menu" }).click();
    await page.getByRole("menuitem", { name: /sign out/i }).click();
    await expect(page).toHaveURL(/\/sign-in/, { timeout: 30_000 });
    await page.waitForFunction(() => window.Clerk?.loaded === true, undefined, { timeout: 30_000 });
    expect(await page.evaluate(() => Boolean(window.Clerk?.session)), "no Clerk session after the sign-out").toBe(false);
    // A protected page no longer opens with this browser: it sends the visitor back to sign-in.
    await page.goto(`/projects/${projectId}/documents`);
    await expect(page).toHaveURL(/\/sign-in/, { timeout: 30_000 });
  });

  const browser = page.context().browser();
  if (!browser) throw new Error("PJ01_RELOGIN_NO_BROWSER");
  // A brand-new context: no cookies, no local storage. Nothing of the first session can carry over.
  const context = await browser.newContext({ baseURL, storageState: { cookies: [], origins: [] } });
  const reloginPage = await context.newPage();
  try {
    await recorder.step("PJ01-S18", "Sign in again as the same user in a fresh browser context", async () => {
      await signInAsJourneyUser(reloginPage, baseURL);
      const userAfter = await clerkUserId(reloginPage);
      expect(userAfter, "a signed-in Clerk user after the new login").toBeTruthy();
      expect(userAfter === userBefore, "the new login is the same Clerk user").toBe(true);
      recorder.record("relogin.sameUser", true);
      recorder.record("relogin.method", "clerk-testing sign-in token, fresh context, empty storage state (not a restored session)");
    });

    const after = await recorder.step("PJ01-S19", "Same project, documents, revisions, alerts and human decisions after the new login", async () => {
      // Reach the project the way a person does: from the list, by its name.
      await reloginPage.getByText(before.project.name, { exact: true }).first().click();
      await expect(reloginPage).toHaveURL(new RegExp(`/projects/${projectId}`), { timeout: 30_000 });
      const snapshot = await readPersistedState(reloginPage, { projectId, documentId });
      expect(snapshot, "everything the first session left is found unchanged").toEqual(before);
      recorder.record("relogin.after", {
        documents: snapshot.documents.length,
        revisions: snapshot.revisions.length,
        alerts: snapshot.alerts.length,
        decisions: snapshot.decisions.length,
        identical: true,
      });
      return snapshot;
    });

    await recorder.step("PJ01-S20", "Current State and the review queue after the new login still rest on revision B", async () => {
      await assertCurrentStateThroughNavigation(reloginPage, recorder, {
        projectId,
        phase: "approved",
        approvedAt: second.revisionReview?.approvedAt ?? second.whatChanged.occurredAt,
        revisionTrace: {
          trusted: {
            revisionId: second.whatChanged.targetRevisionId,
            blobHash: sha256(contractBPdfPath(loadContractBManifest())),
          },
        },
      });
      await recorder.screenshot(reloginPage, "s20-current-state-after-relogin");
    });

    return { before, after };
  } finally {
    await context.close();
  }
}
