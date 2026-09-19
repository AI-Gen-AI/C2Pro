/**
 * PJ-01 step H judge: the What Changed? outcome of a real revision B is honest.
 *
 * Pure: the browser harness captures the application's own timeline and change-detail responses
 * and asks this module whether they state the real change — the declared facts, before and after,
 * bound to both immutable revisions — without false changes or bookkeeping shown as results.
 */

export const CHANGE_CAUSES = ["BUSINESS_STATE_CHANGED", "NEWLY_DISCOVERED"] as const;

export interface TimelineItem {
  event_id: string;
  occurred_at: string;
  event_type: string;
  state: string;
  change_cause: string | null;
  confidence: number | null;
  document_id: string | null;
  provenance: Record<string, unknown>;
}

export interface ChangeEntry {
  change_type?: string;
  anchor?: string;
  before?: Record<string, unknown> | null;
  after?: Record<string, unknown> | null;
  evidence_refs?: unknown[];
  semantic_summary?: string;
}

export interface ChangeDetail extends TimelineItem {
  changes: ChangeEntry[];
  evidence_refs: unknown[];
}

export interface RevisionChangeExpectation {
  documentId: string;
  sourceRevisionId: string;
  targetRevisionId: string;
  sourceBlobHash: string;
  targetBlobHash: string;
  changeCause: string;
  changedFacts: { key: string; before_text: string; after_text: string }[];
  controlTexts: string[];
}

export interface WhatChangedViolation {
  code: string;
  detail: string;
}

const normalise = (value: unknown): string => JSON.stringify(value ?? null).replace(/\s+/g, " ");
const textOf = (value: string): string => value.replace(/\s+/g, " ").trim();

export function findRevisionChange(items: TimelineItem[], expectation: RevisionChangeExpectation): TimelineItem | null {
  return (
    items.find(
      (item) =>
        item.event_type === "revision.changed" &&
        item.document_id === expectation.documentId &&
        item.provenance?.target_revision_id === expectation.targetRevisionId,
    ) ?? null
  );
}

export function evaluateTimeline(items: TimelineItem[], expectation: RevisionChangeExpectation): WhatChangedViolation[] {
  const violations: WhatChangedViolation[] = [];
  const target = findRevisionChange(items, expectation);
  if (!target) {
    violations.push({ code: "MISSING_REVISION_CHANGE", detail: `no revision.changed item for revision ${expectation.targetRevisionId}` });
  } else {
    if (target.change_cause !== expectation.changeCause) {
      violations.push({ code: "UNEXPECTED_CHANGE_CAUSE", detail: `cause ${target.change_cause} != ${expectation.changeCause}` });
    }
    if (target.state !== "ready") {
      violations.push({ code: "CHANGE_NOT_SETTLED", detail: `state ${target.state}` });
    }
  }

  for (const item of items) {
    if (item.change_cause !== null && !(CHANGE_CAUSES as readonly string[]).includes(item.change_cause)) {
      violations.push({ code: "UNKNOWN_CHANGE_CAUSE", detail: `${item.event_id}: ${item.change_cause}` });
    }
    if (item.event_type === "revision.analyzed" && item.state === "ready" && item.change_cause === null) {
      violations.push({ code: "FALSE_NO_CHANGE", detail: `${item.event_id}: an analysis snapshot is shown as a no-change result` });
    }
    if (target && item.event_type === "revision.ingested" && item.document_id === expectation.documentId) {
      violations.push({ code: "PERPETUAL_PROCESSING", detail: `${item.event_id}: an upload of an analysed document is still shown as processing` });
    }
  }
  return violations;
}

export function evaluateChangeDetail(detail: ChangeDetail, expectation: RevisionChangeExpectation): WhatChangedViolation[] {
  const violations: WhatChangedViolation[] = [];
  const provenance = detail.provenance ?? {};
  const mismatched = (
    [
      ["source_revision_id", expectation.sourceRevisionId],
      ["target_revision_id", expectation.targetRevisionId],
      ["source_blob_hash", expectation.sourceBlobHash],
      ["target_blob_hash", expectation.targetBlobHash],
    ] as const
  ).filter(([key, value]) => provenance[key] !== value);
  if (mismatched.length > 0) {
    violations.push({ code: "PROVENANCE_MISMATCH", detail: mismatched.map(([key]) => key).join(", ") });
  }
  if (detail.change_cause !== expectation.changeCause) {
    violations.push({ code: "UNEXPECTED_CHANGE_CAUSE", detail: `cause ${detail.change_cause}` });
  }
  if (detail.changes.length !== expectation.changedFacts.length) {
    violations.push({
      code: "FALSE_CHANGE_COUNT",
      detail: `${detail.changes.length} changes for ${expectation.changedFacts.length} declared facts`,
    });
  }
  for (const fact of expectation.changedFacts) {
    if (!detail.changes.some((change) => normalise(change.before).includes(textOf(fact.before_text)))) {
      violations.push({ code: "MISSING_BEFORE", detail: `${fact.key}: "${fact.before_text}" not in any before` });
    }
    if (!detail.changes.some((change) => normalise(change.after).includes(textOf(fact.after_text)))) {
      violations.push({ code: "MISSING_AFTER", detail: `${fact.key}: "${fact.after_text}" not in any after` });
    }
  }
  if (detail.evidence_refs.length === 0 || detail.changes.some((change) => (change.evidence_refs ?? []).length === 0)) {
    violations.push({ code: "MISSING_EVIDENCE", detail: "a change without evidence references" });
  }
  for (const control of expectation.controlTexts) {
    if (detail.changes.some((change) => `${normalise(change.before)} ${normalise(change.after)}`.includes(textOf(control)))) {
      violations.push({ code: "CONTROL_FACT_REPORTED_CHANGED", detail: `"${control}" appears in a reported change` });
    }
  }
  return violations;
}
