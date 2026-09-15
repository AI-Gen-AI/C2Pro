/**
 * TS-UT-PJ01-WHAT-CHANGED-001 — PJ-01 step H judge: the real revision B outcome is honest.
 */
import { describe, expect, it } from "vitest";

import {
  evaluateChangeDetail,
  evaluateTimeline,
  findRevisionChange,
  type ChangeDetail,
  type RevisionChangeExpectation,
  type TimelineItem,
} from "./what-changed-evaluator";

const expectation: RevisionChangeExpectation = {
  documentId: "doc-1",
  sourceRevisionId: "rev-a",
  targetRevisionId: "rev-b",
  sourceBlobHash: "a".repeat(64),
  targetBlobHash: "b".repeat(64),
  changeCause: "BUSINESS_STATE_CHANGED",
  changedFacts: [
    { key: "contract_price", before_text: "2,400,000.00 EUR", after_text: "2,650,000.00 EUR" },
    { key: "practical_completion_date", before_text: "no later than 31/12/2025", after_text: "no later than 31/03/2026" },
  ],
  controlTexts: ["governed by Spanish law", "EN 1090-2 execution class EXC3"],
};

function change(overrides: Partial<TimelineItem> = {}): TimelineItem {
  return {
    event_id: "evt-change",
    occurred_at: "2026-09-14T10:00:00",
    event_type: "revision.changed",
    state: "ready",
    change_cause: "BUSINESS_STATE_CHANGED",
    confidence: 1,
    document_id: "doc-1",
    provenance: {
      source_revision_id: "rev-a",
      target_revision_id: "rev-b",
      source_blob_hash: "a".repeat(64),
      target_blob_hash: "b".repeat(64),
      diff_engine_version: "p0c-structural-l1-v1",
    },
    ...overrides,
  };
}

function detail(overrides: Partial<ChangeDetail> = {}): ChangeDetail {
  return {
    ...change(),
    changes: [
      {
        change_type: "modified",
        anchor: "AUTO-002",
        before: { full_text: "2.1 The total contract price is 2,400,000.00 EUR" },
        after: { full_text: "2.1 The total contract price is 2,650,000.00 EUR" },
        evidence_refs: [{ locator: "clause_code=AUTO-002" }],
      },
      {
        change_type: "modified",
        anchor: "AUTO-003",
        before: { full_text: "Practical Completion no later than 31/12/2025" },
        after: { full_text: "Practical Completion no later than 31/03/2026" },
        evidence_refs: [{ locator: "clause_code=AUTO-003" }],
      },
    ],
    evidence_refs: [{ locator: "clause_code=AUTO-002" }],
    ...overrides,
  };
}

describe("PJ-01 What Changed? timeline judge", () => {
  it("finds the revision B business change and accepts an honest timeline", () => {
    const items = [change()];
    expect(findRevisionChange(items, expectation)?.event_id).toBe("evt-change");
    expect(evaluateTimeline(items, expectation)).toEqual([]);
  });

  it("reports a missing change, a wrong cause and an unfinished change", () => {
    expect(evaluateTimeline([], expectation).map((v) => v.code)).toEqual(["MISSING_REVISION_CHANGE"]);
    expect(evaluateTimeline([change({ change_cause: "NEWLY_DISCOVERED" })], expectation).map((v) => v.code)).toContain(
      "UNEXPECTED_CHANGE_CAUSE",
    );
    expect(evaluateTimeline([change({ state: "processing" })], expectation).map((v) => v.code)).toContain(
      "CHANGE_NOT_SETTLED",
    );
  });

  it("rejects bookkeeping shown as results: false no-change and perpetual processing", () => {
    const falseNoChange = change({ event_id: "evt-snapshot", event_type: "revision.analyzed", change_cause: null });
    const stuck = change({
      event_id: "evt-ingested",
      event_type: "revision.ingested",
      state: "processing",
      change_cause: null,
      provenance: {},
    });
    const codes = evaluateTimeline([change(), falseNoChange, stuck], expectation).map((v) => v.code);
    expect(codes).toContain("FALSE_NO_CHANGE");
    expect(codes).toContain("PERPETUAL_PROCESSING");
  });

  it("rejects a change cause outside the canonical vocabulary", () => {
    expect(evaluateTimeline([change(), change({ event_id: "x", change_cause: "SOMETHING_ELSE" })], expectation).map((v) => v.code)).toContain(
      "UNKNOWN_CHANGE_CAUSE",
    );
  });
});

describe("PJ-01 What Changed? detail judge", () => {
  it("accepts before/after evidence for exactly the declared facts", () => {
    expect(evaluateChangeDetail(detail(), expectation)).toEqual([]);
  });

  it("requires revision identity and content hashes in the provenance", () => {
    const wrong = detail({ provenance: { ...change().provenance, source_blob_hash: "c".repeat(64) } });
    expect(evaluateChangeDetail(wrong, expectation).map((v) => v.code)).toEqual(["PROVENANCE_MISMATCH"]);
  });

  it("reports missing before/after wording and missing evidence", () => {
    const [price, completion] = detail().changes;
    const codes = evaluateChangeDetail(
      detail({ changes: [{ ...price, after: null, evidence_refs: [] }, completion], evidence_refs: [] }),
      expectation,
    ).map((v) => v.code);
    expect(codes).toContain("MISSING_AFTER");
    expect(codes).toContain("MISSING_EVIDENCE");
  });

  it("reports false changes: extra changes or a control fact reported as changed", () => {
    const [price, completion] = detail().changes;
    const control = { change_type: "modified", anchor: "AUTO-006", before: { full_text: "governed by Spanish law" }, after: { full_text: "governed by French law" }, evidence_refs: [{}] };
    const codes = evaluateChangeDetail(detail({ changes: [price, completion, control] }), expectation).map((v) => v.code);
    expect(codes).toContain("FALSE_CHANGE_COUNT");
    expect(codes).toContain("CONTROL_FACT_REPORTED_CHANGED");
  });
});
