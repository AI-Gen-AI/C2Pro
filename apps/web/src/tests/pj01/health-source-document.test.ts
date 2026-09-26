/**
 * TS-UT-PJ01-HEALTH-EVIDENCE-001 — PJ-01 Health → Evidence judge.
 *
 * The Health assessment must name the uploaded document as its source, and the Evidence
 * workspace a user reaches from it must be that exact document with the linked clause active.
 */
import { describe, expect, it } from "vitest";

import { evaluateEvidenceLanding, evaluateHealthSourceDocument } from "./health-evaluator";

const DOC = "11111111-1111-4111-8111-111111111111";
const CLAUSE = "22222222-2222-4222-8222-222222222222";

describe("PJ-01 Health source document", () => {
  it("accepts an assessment attributed to the uploaded document", () => {
    expect(evaluateHealthSourceDocument({ single_document_coverage: { document_id: DOC, assessments: [] } }, DOC)).toEqual([]);
  });

  it("rejects an unattributed or foreign source document", () => {
    expect(evaluateHealthSourceDocument({ single_document_coverage: { assessments: [] } }, DOC).map((v) => v.code)).toEqual([
      "SOURCE_DOCUMENT_MISSING",
    ]);
    expect(
      evaluateHealthSourceDocument({ single_document_coverage: { document_id: "other", assessments: [] } }, DOC).map((v) => v.code),
    ).toEqual(["SOURCE_DOCUMENT_MISMATCH"]);
  });
});

describe("PJ-01 Evidence landing", () => {
  it("accepts the exact document with the linked clause active", () => {
    expect(
      evaluateEvidenceLanding(
        { url: `http://x/projects/p/evidence?documentId=${DOC}&highlightId=${CLAUSE}`, activeEntityId: CLAUSE, unavailableNotice: null },
        { documentId: DOC, clauseId: CLAUSE },
      ),
    ).toEqual([]);
  });

  it("rejects another document, an inactive clause or an unavailable notice", () => {
    const codes = evaluateEvidenceLanding(
      { url: "http://x/projects/p/evidence?documentId=other&highlightId=nope", activeEntityId: null, unavailableNotice: "gone" },
      { documentId: DOC, clauseId: CLAUSE },
    ).map((v) => v.code);
    expect(codes).toEqual(["EVIDENCE_WRONG_DOCUMENT", "EVIDENCE_WRONG_CLAUSE", "EVIDENCE_CLAUSE_NOT_ACTIVE", "EVIDENCE_LINK_UNAVAILABLE"]);
  });
});
