import { describe, expect, it } from "vitest";

import type { CurrentStateReportLike } from "./current-state-evaluator";
import {
  evaluateApprovedRevisionCurrentState,
  evaluateHealthEvidenceRevision,
  evaluatePendingRevisionCurrentState,
  parseInstant,
  revisionOfClause,
} from "./revision-authority-evaluator";

const A = "rev-a";
const B = "rev-b";
const entity = (id: string, revision: string | null) => ({
  id,
  metadata: { evidence_location: revision === null ? null : { revision_id: revision } },
});

const report = (overrides: {
  lifecycle?: string;
  attention?: string[];
  hitl?: string;
  healthAsOf?: string;
}): CurrentStateReportLike => ({
  sections: {
    documents: {
      status: "available",
      data: {
        total: 1,
        by_type: { contract: 1 },
        items: [{ id: "doc", lifecycle_status: overrides.lifecycle ?? "analyzed" }],
      },
    },
    executive_summary: {
      status: "available",
      data: { attention_items: (overrides.attention ?? []).map((kind) => ({ kind })) },
    },
    hitl: { status: overrides.hitl ?? "empty" },
    health: { status: "available", source_as_of: overrides.healthAsOf ?? "2026-10-25T13:09:34.042092Z" },
  },
});

describe("parseInstant", () => {
  it("reads a zone-less instant as UTC, like the API stores it", () => {
    expect(parseInstant("2026-10-25T13:09:33.5")).toBe(Date.UTC(2026, 9, 25, 13, 9, 33, 500));
    expect(parseInstant("2026-10-25T13:09:33.500Z")).toBe(parseInstant("2026-10-25T13:09:33.5"));
    expect(parseInstant("2026-10-25T15:09:33.500+02:00")).toBe(parseInstant("2026-10-25T13:09:33.5"));
  });
});

describe("evaluateHealthEvidenceRevision", () => {
  const entities = [entity("c1", A), entity("c2", B)];

  it("accepts a clause of the authorized revision", () => {
    expect(revisionOfClause(entities, "c1")).toBe(A);
    expect(evaluateHealthEvidenceRevision({ clauseId: "c1", entities }, { expectedRevisionId: A, phase: "pending" })).toEqual([]);
  });

  it("rejects Health resting on the pending revision before approval", () => {
    const [violation] = evaluateHealthEvidenceRevision(
      { clauseId: "c2", entities },
      { expectedRevisionId: A, otherRevisionId: B, phase: "pending" },
    );
    expect(violation.code).toBe("HEALTH_RESTS_ON_WRONG_REVISION");
    expect(violation.detail).toContain("OTHER revision");
  });

  it("rejects Health still resting on revision A after B was approved", () => {
    const [violation] = evaluateHealthEvidenceRevision(
      { clauseId: "c1", entities },
      { expectedRevisionId: B, otherRevisionId: A, phase: "approved" },
    );
    expect(violation.code).toBe("HEALTH_RESTS_ON_WRONG_REVISION");
  });

  it("treats an unresolved citation as a violation, not a pass", () => {
    expect(evaluateHealthEvidenceRevision({ clauseId: "gone", entities }, { expectedRevisionId: A, phase: "p" })[0].code).toBe(
      "EVIDENCE_CLAUSE_UNRESOLVED",
    );
    expect(
      evaluateHealthEvidenceRevision({ clauseId: "c3", entities: [entity("c3", null)] }, { expectedRevisionId: A, phase: "p" })[0].code,
    ).toBe("EVIDENCE_CLAUSE_UNRESOLVED");
  });
});

describe("evaluatePendingRevisionCurrentState", () => {
  it("accepts a report that says a revision waits for a decision", () => {
    expect(
      evaluatePendingRevisionCurrentState(
        report({ lifecycle: "analysis_pending", attention: ["hitl_pending", "documents_awaiting_analysis"], hitl: "available" }),
      ),
    ).toEqual([]);
  });

  it("rejects a pending revision presented as analyzed and undisclosed", () => {
    const codes = evaluatePendingRevisionCurrentState(report({ lifecycle: "analyzed", hitl: "empty" })).map((v) => v.code);
    expect(codes).toEqual(["PENDING_REVISION_SHOWN_AS_ANALYZED", "PENDING_REVISION_NOT_DISCLOSED", "PENDING_DECISION_NOT_DISCLOSED"]);
  });
});

describe("evaluateApprovedRevisionCurrentState", () => {
  const approvedAt = "2026-10-25T13:09:33.088392";

  it("accepts a report recomputed after the approval with nothing pending", () => {
    expect(evaluateApprovedRevisionCurrentState(report({}), { approvedAt })).toEqual([]);
  });

  it("rejects the pre-approval Health snapshot", () => {
    const [violation] = evaluateApprovedRevisionCurrentState(report({ healthAsOf: "2026-10-25T13:08:07.133568Z" }), { approvedAt });
    expect(violation.code).toBe("HEALTH_PREDATES_APPROVAL");
  });

  it("rejects leftovers of the pending state", () => {
    const codes = evaluateApprovedRevisionCurrentState(
      report({ lifecycle: "analysis_pending", attention: ["documents_awaiting_analysis"], hitl: "available" }),
      { approvedAt },
    ).map((v) => v.code);
    expect(codes).toEqual(["APPROVED_REVISION_NOT_ANALYZED", "APPROVED_REVISION_STILL_PENDING", "APPROVED_DECISION_STILL_PENDING"]);
  });
});
