/**
 * TS-UT-PJ01-HEALTH-001 — six canonical Health categories, honest nulls, predictable fixture.
 */
import { describe, expect, it } from "vitest";

import {
  CANONICAL_CATEGORIES,
  evaluateHealthTileText,
  evaluateHealthVector,
  type CategoryAssessmentPayload,
  type HealthVectorPayload,
} from "./health-evaluator";

const UUID = (n: number) => `00000000-0000-4000-8000-${String(n).padStart(12, "0")}`;

function present(category: string, ids: string[]): CategoryAssessmentPayload {
  return { category, state: "present", evidence_count: ids.length, evidence_clause_ids: ids, missing_data: [], gap: null };
}

function insufficient(category: string): CategoryAssessmentPayload {
  return {
    category,
    state: "insufficient_evidence",
    evidence_count: 0,
    evidence_clause_ids: [],
    missing_data: [`${category.toLowerCase()} not detected`],
    gap: { category, action: `Upload evidence to assess ${category}.` },
  };
}

function vector(assessments: CategoryAssessmentPayload[], granularity: string | null = "clause"): HealthVectorPayload {
  return { single_document_coverage: { assessments }, single_document_evidence_granularity: granularity };
}

const allPresent = () => CANONICAL_CATEGORIES.map((category, index) => present(category, [UUID(index + 1)]));
const codes = (violations: { code: string }[]) => violations.map((v) => v.code);

describe("evaluateHealthVector", () => {
  it("accepts six evidence-backed categories with disclosed clause granularity", () => {
    expect(evaluateHealthVector(vector(allPresent()))).toEqual([]);
  });

  it("reports an absent assessment as COVERAGE_MISSING, never as six unknowns", () => {
    expect(codes(evaluateHealthVector({ single_document_coverage: null }))).toEqual(["COVERAGE_MISSING"]);
  });

  it("requires exactly the six canonical categories", () => {
    const five = allPresent().slice(0, 5);
    expect(codes(evaluateHealthVector(vector(five)))).toContain("CATEGORY_SET_MISMATCH");
    const duplicated = [...allPresent(), present("SCOPE", [UUID(99)])];
    expect(codes(evaluateHealthVector(vector(duplicated)))).toContain("DUPLICATE_CATEGORY");
  });

  it("enforces the P0b honest-null invariants", () => {
    const bad = allPresent();
    bad[0] = { ...present("SCOPE", []), evidence_count: 0 };
    bad[1] = { ...present("BUDGET", [UUID(2), UUID(2)]), evidence_count: 2 };
    bad[2] = { ...insufficient("TIME"), evidence_count: 1, evidence_clause_ids: [UUID(3)] };
    bad[3] = { ...insufficient("TECHNICAL"), gap: null };
    bad[4] = { ...insufficient("LEGAL"), missing_data: [] };
    bad[5] = present("QUALITY", ["not-a-uuid"]);
    const found = codes(evaluateHealthVector(vector(bad)));
    expect(found).toEqual(
      expect.arrayContaining([
        "PRESENT_WITHOUT_EVIDENCE",
        "DUPLICATE_EVIDENCE_ID",
        "INSUFFICIENT_WITH_EVIDENCE",
        "INSUFFICIENT_WITHOUT_GAP",
        "INSUFFICIENT_WITHOUT_MISSING_DATA",
        "CLAUSE_ID_NOT_UUID",
      ]),
    );
  });

  it("flags evidence_count that disagrees with the evidence ids", () => {
    const bad = allPresent();
    bad[0] = { ...bad[0], evidence_count: 3 };
    expect(codes(evaluateHealthVector(vector(bad)))).toContain("EVIDENCE_COUNT_MISMATCH");
  });

  it("requires the evidence granularity to be disclosed", () => {
    expect(codes(evaluateHealthVector(vector(allPresent(), null)))).toContain("GRANULARITY_UNDISCLOSED");
  });

  it("compares against fixture expectations when given", () => {
    const actual = allPresent();
    actual[2] = insufficient("TIME");
    const violations = evaluateHealthVector(vector(actual), {
      granularity: "clause",
      categories: Object.fromEntries(CANONICAL_CATEGORIES.map((c) => [c, { state: "present", evidenceCount: 1 }])),
    });
    expect(violations).toContainEqual(expect.objectContaining({ code: "EXPECTED_STATE_MISMATCH", category: "TIME" }));
    expect(
      codes(evaluateHealthVector(vector(allPresent(), "document"), { granularity: "clause" })),
    ).toContain("GRANULARITY_MISMATCH");
  });
});

describe("evaluateHealthTileText", () => {
  it("rejects a fabricated zero on a category without evidence", () => {
    expect(evaluateHealthTileText("TIME", "insufficient_evidence", "TIME 0%")).toEqual([
      expect.objectContaining({ code: "FABRICATED_ZERO", category: "TIME" }),
    ]);
    expect(evaluateHealthTileText("TIME", "insufficient_evidence", "TIME Score: 0")).toHaveLength(1);
  });

  it("accepts the honest unknown label and evidence counts", () => {
    expect(evaluateHealthTileText("TIME", "insufficient_evidence", "TIME Unknown / Insufficient evidence")).toEqual([]);
    expect(evaluateHealthTileText("SCOPE", "present", "SCOPE Evidence found 1")).toEqual([]);
  });

  it("requires the unknown label on a category without evidence", () => {
    expect(evaluateHealthTileText("LEGAL", "insufficient_evidence", "LEGAL")).toEqual([
      expect.objectContaining({ code: "UNKNOWN_NOT_LABELLED", category: "LEGAL" }),
    ]);
  });
});
