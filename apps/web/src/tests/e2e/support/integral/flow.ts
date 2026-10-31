/**
 * Building blocks of the integral S1–S8 runner. Each one does what a signed-in person does (UI) or what the
 * application's own authenticated API answers; none writes to the database and none forges an event.
 */
import { expect, type Locator, type Page, type Response } from "@playwright/test";

import { clickProjectTab, readProjectTabs } from "../pj01/health";
import type { ChangeDetail, TimelineItem } from "../../../pj01/what-changed-evaluator";
import type { Pj01RunRecorder } from "../pj01/run-recorder";
import { callApi, itemsOf, str, strOrNull, waitFor, type Json } from "./api";

export const SETTLE_BUDGET_MS = 240_000;

/** Click the project tab whose link points at `/projects/{id}/<segment>` (tabs are links; no typed URL). */
export async function openProjectTab(page: Page, projectId: string, segment: string): Promise<void> {
  const tabs = await readProjectTabs(page);
  const tab = tabs.find((candidate) => new RegExp(`/projects/${projectId}/${segment}(?:[/?#]|$)`).test(candidate.href));
  expect(tab, `a visible "${segment}" project tab (tabs: ${tabs.map((t) => t.name).join(", ")})`).toBeTruthy();
  await page.locator(`nav[aria-label="Project tabs"] a[href="${tab?.href}"]`).first().click();
  await page.waitForURL(new RegExp(`/projects/${projectId}/${segment}`), { timeout: 30_000 });
}
const FAILED_STATES = ["error", "failed_retryable", "needs_changes"];

// ── documents ──────────────────────────────────────────────────────────────────────────────────────────────
export async function listDocuments(page: Page, projectId: string): Promise<Json[]> {
  const answer = await callApi(page, `/api/v1/projects/${projectId}/documents?limit=100`);
  expect(answer.status, "documents readable").toBe(200);
  return itemsOf(answer.data);
}

/** Poll the application until the document reaches one of `accept`; any failure state is a hard error. */
export async function waitForDocument(
  page: Page,
  projectId: string,
  documentId: string,
  accept: string[],
  timeoutMs = SETTLE_BUDGET_MS,
): Promise<Json> {
  return waitFor(
    page,
    `document ${documentId} reaches ${accept.join("|")}`,
    async () => {
      const document = (await listDocuments(page, projectId)).find((item) => item.id === documentId);
      const state = str(document?.lifecycle_status);
      if (document && accept.includes(state)) return document;
      if (FAILED_STATES.includes(state) && !accept.includes(state)) {
        throw new Error(`INTEGRAL_DOCUMENT_FAILED: ${documentId} is ${state}`);
      }
      return null;
    },
    { timeoutMs },
  );
}

export interface RevisionRow {
  revNo: number | null;
  revisionId: string;
  blobHash: string;
  trustState: string | null;
  isCurrent: boolean;
  currentBasis: string | null;
}

export async function readRevisions(page: Page, documentId: string): Promise<RevisionRow[]> {
  const answer = await callApi(page, `/api/v1/documents/${documentId}/revisions`);
  expect(answer.status, `revisions of ${documentId} readable`).toBe(200);
  return itemsOf(answer.data)
    .map((row) => ({
      revNo: typeof row.rev_no === "number" ? row.rev_no : null,
      revisionId: str(row.revision_id),
      blobHash: str(row.blob_hash),
      trustState: strOrNull(row.trust_state),
      isCurrent: row.is_current === true,
      currentBasis: strOrNull(row.current_basis),
    }))
    .sort((a, b) => (a.revNo ?? 0) - (b.revNo ?? 0) || a.revisionId.localeCompare(b.revisionId));
}

// ── human decisions through the review queue ───────────────────────────────────────────────────────────────
export interface HumanDecision {
  itemId: string;
  rowId: string;
  status: string;
  decidedBy: string;
  decidedAt: string;
  generation: number | null;
}

/**
 * Open the document's review from its row (as a person does) and return the card of THAT document's item: the
 * queue may hold other documents' items, so the decision is always addressed to the card of this item.
 */
async function openReviewCard(
  page: Page,
  recorder: Pj01RunRecorder,
  projectId: string,
  documentId: string,
): Promise<{ itemId: string; card: Locator }> {
  const document = (await listDocuments(page, projectId)).find((item) => item.id === documentId);
  const itemId = str(document?.review_item_id);
  if (!itemId) throw new Error(`INTEGRAL_NO_REVIEW_ITEM: ${documentId} offers no review item (state ${str(document?.lifecycle_status)})`);
  await clickProjectTab(page, recorder, projectId, "documents", "DOCUMENTS_TAB_NOT_NAVIGABLE");
  await page.waitForURL(new RegExp(`/projects/${projectId}/documents`), { timeout: 30_000 });
  const row = page.getByTestId(`document-row-${documentId}`);
  await expect(row).toBeVisible({ timeout: 30_000 });
  await row.getByTestId("document-review-cta").first().click();
  await expect(page.getByTestId("review-page")).toBeVisible({ timeout: 30_000 });
  const card = page.getByTestId(`review-item-${itemId}`);
  await expect(card, "the review card of this document's item").toBeVisible({ timeout: 60_000 });
  return { itemId, card };
}

const decisionFrom = async (response: Response): Promise<HumanDecision> => {
  expect(response.status(), await response.text().catch(() => "")).toBeLessThan(300);
  const body = (await response.json()) as Json & { item_data?: { thread_id?: string } };
  const generation = Number(str(body.item_data?.thread_id).match(/:g(\d+):/)?.[1] ?? NaN);
  return {
    itemId: str(body.item_id),
    rowId: str(body.row_id),
    status: str(body.current_status),
    decidedBy: str(body.approved_by),
    decidedAt: str(body.approved_at),
    generation: Number.isNaN(generation) ? null : generation,
  };
};

/** The FINAL human act on a pending review: approve it (confirm dialog), through the review page. */
export async function approveThroughUi(
  page: Page,
  recorder: Pj01RunRecorder,
  options: { projectId: string; documentId: string },
): Promise<HumanDecision> {
  const { itemId, card } = await openReviewCard(page, recorder, options.projectId, options.documentId);
  const approve = card.getByTestId(`approve-${itemId}`);
  await expect(approve).toBeEnabled({ timeout: 120_000 });
  await approve.click();
  const dialog = page.getByRole("dialog", { name: /approve review item/i });
  await expect(dialog).toBeVisible();
  const approved = page.waitForResponse(
    (response: Response) =>
      response.request().method() === "POST" && /\/hitl\/queue\/[^/]+\/approve/.test(new URL(response.url()).pathname),
    { timeout: 120_000 },
  );
  await dialog.getByRole("button", { name: /confirm approve/i }).click();
  return decisionFrom(await approved);
}

/** Open the document's review and REJECT it, with the reason typed in the dialog (UI only). */
export async function rejectThroughUi(
  page: Page,
  recorder: Pj01RunRecorder,
  options: { projectId: string; documentId: string; reason: string },
): Promise<HumanDecision> {
  const { itemId, card } = await openReviewCard(page, recorder, options.projectId, options.documentId);
  const rejectAction = card.getByTestId(`reject-${itemId}`);
  await expect(rejectAction).toBeEnabled({ timeout: 120_000 });
  await rejectAction.click();
  const dialog = page.getByRole("dialog", { name: /reject review item/i });
  await expect(dialog).toBeVisible();
  const confirm = dialog.getByRole("button", { name: /confirm reject/i });
  await expect(confirm, "a rejection cannot be confirmed without a reason").toBeDisabled();
  await dialog.getByLabel(/rejection reason/i).fill(options.reason);
  await expect(confirm).toBeEnabled();
  const rejected = page.waitForResponse(
    (response: Response) =>
      response.request().method() === "POST" && /\/hitl\/queue\/[^/]+\/reject/.test(new URL(response.url()).pathname),
    { timeout: 120_000 },
  );
  await confirm.click();
  return decisionFrom(await rejected);
}

// ── Health, Coherence ──────────────────────────────────────────────────────────────────────────────────────
export interface HealthRead {
  computedAt: string;
  compositeScore: number | null;
  compositeBand: string;
  assessments: Array<{ category: string; state: string }>;
}

export async function readHealth(page: Page, projectId: string): Promise<HealthRead | null> {
  const answer = await callApi(page, `/api/v1/projects/${projectId}/health`);
  if (answer.status !== 200) return null;
  const body = answer.data as {
    computed_at?: string;
    composite_score?: number | null;
    composite_band?: string;
    single_document_coverage?: { assessments?: Array<{ category: string; state: string }> } | null;
  };
  const assessments = body.single_document_coverage?.assessments ?? [];
  return {
    computedAt: body.computed_at ?? "",
    compositeScore: body.composite_score ?? null,
    compositeBand: body.composite_band ?? "",
    assessments: assessments
      .map((a) => ({ category: a.category, state: a.state }))
      .sort((a, b) => a.category.localeCompare(b.category)),
  };
}

export async function waitForSixDimensionHealth(page: Page, projectId: string): Promise<HealthRead> {
  return waitFor(
    page,
    "Health with six persisted assessments",
    async () => {
      const health = await readHealth(page, projectId);
      return health && health.assessments.length === 6 && new Set(health.assessments.map((a) => a.category)).size === 6
        ? health
        : null;
    },
    { timeoutMs: SETTLE_BUDGET_MS },
  );
}

export interface DashboardRead {
  globalScore: number | null;
  scoreVersion: string | null;
  scoreReason: string | null;
  missingDimensions: string[];
  subScores: Record<string, number | null>;
  methodologyVersion: string | null;
  trustedScore: number | null;
  pendingReviewCount: number;
  alertCount: number;
  documentCount: number;
  weights: Record<string, number>;
  evaluatedAt: string;
}

export async function readDashboard(page: Page, projectId: string): Promise<DashboardRead> {
  const answer = await callApi(page, `/api/v1/coherence/dashboard/${projectId}`);
  expect(answer.status, "persisted Coherence dashboard readable").toBe(200);
  const body = answer.data as Json & {
    sub_scores?: Record<string, number | null>;
    weights_used?: Record<string, number>;
    score_missing_dimensions?: string[] | null;
  };
  const sorted = <T>(record: Record<string, T> | undefined): Record<string, T> =>
    Object.fromEntries(Object.entries(record ?? {}).sort(([a], [b]) => a.localeCompare(b)));
  return {
    globalScore: typeof body.global_score === "number" ? body.global_score : null,
    scoreVersion: strOrNull(body.score_version),
    scoreReason: strOrNull(body.score_reason),
    missingDimensions: [...(body.score_missing_dimensions ?? [])].sort(),
    subScores: sorted(body.sub_scores),
    methodologyVersion: strOrNull(body.methodology_version),
    trustedScore: typeof body.trusted_score === "number" ? body.trusted_score : null,
    pendingReviewCount: typeof body.pending_review_count === "number" ? body.pending_review_count : 0,
    alertCount: typeof body.alert_count === "number" ? body.alert_count : 0,
    documentCount: typeof body.document_count === "number" ? body.document_count : 0,
    weights: sorted(body.weights_used),
    evaluatedAt: str(body.last_updated),
  };
}

export interface AlertRow {
  id: string;
  ruleCode: string;
  status: string;
  sourceClauseId: string | null;
}

export async function readAlerts(page: Page, projectId: string): Promise<AlertRow[]> {
  const answer = await callApi(page, `/api/v1/alerts/projects/${projectId}`);
  expect(answer.status, "persisted Alerts readable").toBe(200);
  return itemsOf(answer.data)
    .map((row) => ({
      id: str(row.id),
      ruleCode: str(row.rule_code),
      status: str(row.status),
      sourceClauseId: strOrNull(row.source_clause_id),
    }))
    .sort((a, b) => a.id.localeCompare(b.id));
}

// ── canonical WBS (governed change set, human-approved) ───────────────────────────────────────────────────
export interface WbsBaseline {
  changeSetId: string;
  baselineId: string;
  baselineNo: number;
  rootNodeId: string;
  childNodeId: string;
  treeDigest: string;
  selfApproved: boolean;
  approvalEventId: string;
}

async function must(page: Page, what: string, url: string, body: Json, ok: number[]): Promise<Json> {
  const answer = await callApi(page, url, "POST", body);
  if (!ok.includes(answer.status)) {
    throw new Error(`INTEGRAL_${what}: HTTP ${answer.status} ${JSON.stringify(answer.data).slice(0, 200)}`);
  }
  return answer.data as Json;
}

/** Draft → two nodes → submit → approve, all as the signed-in human through the governed-change API. */
export async function approveCanonicalWbs(page: Page, projectId: string): Promise<WbsBaseline> {
  const base = `/api/v1/projects/${projectId}/wbs-governance/change-sets`;
  const created = await must(
    page,
    "WBS_CREATE",
    base,
    { title: "Integral UAT canonical baseline", description: "Civil works and foundations, approved by the project owner." },
    [201],
  );
  const changeSetId = str(created.id);
  let revision = Number(created.revision);
  const add = async (name: string, code: string, parentId: string | null): Promise<string> => {
    const answer = await must(
      page,
      "WBS_ADD_NODE",
      `${base}/${changeSetId}/commands`,
      { expected_revision: revision, command: { type: "ADD_NODE", node: { name, code }, parent_id: parentId } },
      [200],
    );
    revision = Number(answer.revision);
    return str((answer.node_ids as string[])[0]);
  };
  const rootNodeId = await add("Civil works", "1", null);
  const childNodeId = await add("Foundations", "1.1", rootNodeId);
  const submitted = await must(page, "WBS_SUBMIT", `${base}/${changeSetId}/submit`, { expected_revision: revision }, [200]);
  const applied = await must(
    page,
    "WBS_APPROVE",
    `${base}/${changeSetId}/approve`,
    { expected_revision: Number(submitted.submitted_revision), expected_digest: str(submitted.submitted_digest) },
    [200],
  );
  return {
    changeSetId,
    baselineId: str(applied.baseline_id),
    baselineNo: Number(applied.baseline_no),
    rootNodeId,
    childNodeId,
    treeDigest: str(applied.tree_digest),
    selfApproved: applied.self_approved === true,
    approvalEventId: str(applied.event_id),
  };
}

// ── canonical source → WBS links (each one an explicit human approval) ────────────────────────────────────
export interface LinkAttempt {
  family: "budget" | "schedule" | "technical";
  status: number;
  eventId: string | null;
  detail: string;
}

export async function approveStructuredLink(
  page: Page,
  projectId: string,
  wbs: WbsBaseline,
  source: { family: "budget" | "schedule"; documentId: string; revisionId: string; blobHash: string; locator: string },
): Promise<LinkAttempt> {
  const answer = await callApi(page, `/api/v1/projects/${projectId}/structured-wbs/canonical-links`, "POST", {
    family: source.family,
    source_document_id: source.documentId,
    source_revision_id: source.revisionId,
    expected_blob_hash: source.blobHash,
    source_locator: source.locator,
    expected_wbs_baseline_id: wbs.baselineId,
    expected_wbs_node_id: wbs.childNodeId,
    approval: "APPROVE_CANONICAL_LINK",
    idempotency_key: `integral-${source.family}-${projectId}`.slice(0, 120),
    reason: `The project owner confirms the ${source.family} source row belongs to Foundations (integral UAT).`,
  });
  const body = answer.data as Json;
  return {
    family: source.family,
    status: answer.status,
    eventId: answer.status === 201 ? str(body.event_id) || null : null,
    detail: answer.status === 201 ? "approved" : JSON.stringify(answer.data).slice(0, 240),
  };
}

export async function approveTechnicalLink(
  page: Page,
  projectId: string,
  wbs: WbsBaseline,
  source: { documentId: string; revisionId: string; blobHash: string; section: string },
): Promise<LinkAttempt> {
  const document = await callApi(page, `/api/v1/documents/${source.documentId}?revision_id=${source.revisionId}`);
  if (document.status !== 200) {
    return { family: "technical", status: document.status, eventId: null, detail: "technical document unreadable" };
  }
  const clauses = ((document.data as { clauses?: Json[] }).clauses ?? []).filter((clause) => {
    const entities = clause.extracted_entities as { technical_requirement?: { source_section?: string } } | null;
    return (
      clause.extraction_model === "deterministic-technical-section-v1" &&
      clause.revision_id === source.revisionId &&
      entities?.technical_requirement?.source_section === source.section
    );
  });
  if (clauses.length !== 1) {
    return {
      family: "technical",
      status: 0,
      eventId: null,
      detail: `${clauses.length} eligible technical clause(s) for section ${source.section} on the trusted revision`,
    };
  }
  const root = `/api/v1/projects/${projectId}/technical-wbs`;
  const review = await callApi(page, `${root}/reviews`, "POST", {
    clause_id: str(clauses[0]!.id),
    expected_revision_id: source.revisionId,
    expected_blob_hash: source.blobHash,
    expected_wbs_baseline_id: wbs.baselineId,
    proposed_wbs_node_id: wbs.childNodeId,
    decision: "CONFIRMED_FOR_REVIEW",
    idempotency_key: `integral-technical-review-${projectId}`.slice(0, 120),
    reason: "The project owner confirms the requirement belongs to Foundations (integral UAT).",
  });
  if (review.status !== 201) {
    return { family: "technical", status: review.status, eventId: null, detail: JSON.stringify(review.data).slice(0, 240) };
  }
  const approved = await callApi(page, `${root}/canonical-links`, "POST", {
    review_event_id: str((review.data as Json).event_id),
    expected_wbs_baseline_id: wbs.baselineId,
    expected_wbs_node_id: wbs.childNodeId,
    approval: "APPROVE_CANONICAL_LINK",
    idempotency_key: `integral-technical-approval-${projectId}`.slice(0, 120),
    reason: "Explicit approval of the technical requirement to WBS relation (integral UAT).",
  });
  return {
    family: "technical",
    status: approved.status,
    eventId: approved.status === 201 ? str((approved.data as Json).event_id) || null : null,
    detail: approved.status === 201 ? "approved" : JSON.stringify(approved.data).slice(0, 240),
  };
}

export interface LinkView {
  eventId: string;
  family: string;
  state: string;
  baselineId: string;
  nodeId: string;
  documentId: string;
  revisionId: string;
  blobHash: string;
  locator: string;
  authority: string;
}

export async function readLinks(page: Page, projectId: string): Promise<LinkView[]> {
  const [structured, technical] = await Promise.all([
    callApi(page, `/api/v1/projects/${projectId}/structured-wbs/canonical-links`),
    callApi(page, `/api/v1/projects/${projectId}/technical-wbs/canonical-links`),
  ]);
  expect(structured.status, "structured links readable").toBe(200);
  expect(technical.status, "technical links readable").toBe(200);
  const views: LinkView[] = [];
  for (const row of (structured.data as Json[]) ?? []) {
    views.push({
      eventId: str(row.event_id),
      family: str(row.family),
      state: str(row.state),
      baselineId: str(row.wbs_baseline_id),
      nodeId: str(row.wbs_node_id),
      documentId: str(row.source_document_id),
      revisionId: str(row.source_revision_id),
      blobHash: str(row.source_blob_hash),
      locator: str(row.source_locator),
      authority: str(row.authority),
    });
  }
  for (const row of (technical.data as Json[]) ?? []) {
    views.push({
      eventId: str(row.event_id),
      family: "technical",
      state: str(row.state),
      baselineId: str(row.wbs_baseline_id),
      nodeId: str(row.wbs_node_id),
      documentId: str(row.technical_document_id),
      revisionId: str(row.technical_revision_id),
      blobHash: str(row.source_blob_hash),
      locator: str(row.source_section),
      authority: str(row.authority),
    });
  }
  return views.sort((a, b) => a.family.localeCompare(b.family));
}

// ── What Changed? and Current State around revision B ─────────────────────────────────────────────────────
export interface ChangeRead {
  changeEventId: string;
  sourceRevisionId: string;
  targetRevisionId: string;
  sourceBlobHash: string;
  targetBlobHash: string;
  changeCause: string | null;
  state: string;
  changeCount: number;
  mentionsAddedClause: boolean;
}

/**
 * What Changed? reached through the project tab: the application's own timeline and change detail, without a
 * reload. Judged against the committed A and B files by SHA-256 and by the clause B adds; the revision ids are the
 * application's own (compared with the ledger by the caller).
 */
export async function readWhatChanged(
  page: Page,
  recorder: Pj01RunRecorder,
  options: { projectId: string; documentId: string; marker: string },
): Promise<ChangeRead> {
  const { projectId, documentId } = options;
  const timelines: TimelineItem[][] = [];
  const onTimeline = async (response: Response): Promise<void> => {
    if (response.request().method() !== "GET" || !response.ok()) return;
    if (!new RegExp(`/projects/${projectId}/timeline/?$`).test(new URL(response.url()).pathname)) return;
    try {
      timelines.push(((await response.json()) as { items: TimelineItem[] }).items);
    } catch {
      /* not a timeline body */
    }
  };
  page.on("response", onTimeline);
  try {
    await clickProjectTab(page, recorder, projectId, "changes", "WHAT_CHANGED_TAB_NOT_NAVIGABLE");
    await page.waitForURL(new RegExp(`/projects/${projectId}/changes`), { timeout: 30_000 });
    const latest = (): TimelineItem | undefined =>
      timelines.at(-1)?.find((item) => item.event_type === "revision.changed" && item.document_id === documentId);
    await waitFor(page, "the revision change appears on What Changed", async () => latest() ?? null, { timeoutMs: 180_000, intervalMs: 2_000 });
    const change = latest()!;
    const targetRevisionId = str(change.provenance.target_revision_id);
    const card = page.getByTestId(`change-item-${change.event_id}`);
    await expect(card).toBeVisible({ timeout: 30_000 });
    const detailResponse = page.waitForResponse(
      (response: Response) =>
        response.request().method() === "GET" &&
        new RegExp(`/projects/${projectId}/documents/${documentId}/changes/${targetRevisionId}/?$`).test(new URL(response.url()).pathname),
      { timeout: 60_000 },
    );
    await card.getByRole("link", { name: /view before, after & evidence/i }).click();
    const detail = (await (await detailResponse).json()) as ChangeDetail;
    await expect(page.getByTestId("change-detail-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText("Source evidence unavailable")).toHaveCount(0);
    return {
      changeEventId: change.event_id,
      sourceRevisionId: str(change.provenance.source_revision_id),
      targetRevisionId,
      sourceBlobHash: str(detail.provenance?.source_blob_hash),
      targetBlobHash: str(detail.provenance?.target_blob_hash),
      changeCause: detail.change_cause,
      state: change.state,
      changeCount: detail.changes.length,
      mentionsAddedClause: JSON.stringify(detail.changes).toLowerCase().includes(options.marker.toLowerCase()),
    };
  } finally {
    page.off("response", onTimeline);
  }
}

export interface CurrentStateDocument {
  filename: string;
  lifecycle: string;
  trustedRevision: { revision_id: string; blob_hash: string } | null;
  pendingRevision: { revision_id: string; blob_hash: string } | null;
}

/** The Current State report, regenerated through the Report tab; returns what it says about each document. */
export async function readCurrentState(
  page: Page,
  recorder: Pj01RunRecorder,
  projectId: string,
): Promise<CurrentStateDocument[]> {
  await clickProjectTab(page, recorder, projectId, "report", "REPORT_TAB_NOT_NAVIGABLE");
  await page.waitForURL(new RegExp(`/projects/${projectId}/report`), { timeout: 30_000 });
  const regenerate = page.getByRole("button", { name: /^regenerate$/i });
  await expect(regenerate).toBeEnabled({ timeout: 120_000 });
  const answered = page.waitForResponse(
    (response: Response) =>
      response.request().method() === "GET" &&
      response.ok() &&
      new RegExp(`/projects/${projectId}/reports/current-state/?$`).test(new URL(response.url()).pathname),
    { timeout: 120_000 },
  );
  await regenerate.click();
  const report = (await (await answered).json()) as {
    sections?: { documents?: { data?: { items?: Json[] } } };
  };
  return (report.sections?.documents?.data?.items ?? []).map((item) => ({
    filename: str(item.filename),
    lifecycle: str(item.lifecycle_status),
    trustedRevision: (item.trusted_revision as CurrentStateDocument["trustedRevision"]) ?? null,
    pendingRevision: (item.pending_revision as CurrentStateDocument["pendingRevision"]) ?? null,
  }));
}
