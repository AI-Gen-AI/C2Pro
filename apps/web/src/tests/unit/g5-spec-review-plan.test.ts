import { describe, expect, it } from "vitest";

import {
  assertSyntheticSpecDecisionsPersisted,
  planSyntheticSpecReview,
  type SyntheticReviewContext,
} from "../e2e/support/integral/spec-review-plan";

const REVIEW = "c21c903d-fc92-4e56-a44f-4c60acdaf2e4";
const HASH = "a".repeat(64);
const MODE: SyntheticReviewContext = {
  environment: "test",
  integralUat: "1",
  aiMode: "real-ai",
  aiMock: "0",
};

function doc(count: number, action: string | null = null) {
  return {
    review_row_id: REVIEW,
    artifact_hash: HASH,
    findings: Array.from({ length: count }, (_, ordinal) => ({
      ordinal,
      finding_id: `risk-${ordinal}`,
      source_item_id: `risk-source-${ordinal}`,
      risk: {
        source_quote_status: ordinal % 2 ? "UNVERIFIED" : "VERIFIED",
        source_quote: ordinal % 2 ? null : "A verbatim source sentence",
      },
      current: action ? { action } : null,
    })),
  };
}

describe("G5 synthetic specification review planning", () => {
  it.each([0, 1, 2, 5, 12])("enumerates all %i provider findings without a fixed cap at four", (count) => {
    const plan = planSyntheticSpecReview(200, doc(count), REVIEW, MODE);
    expect(plan.ordinals).toEqual(Array.from({ length: count }, (_, i) => i));
    expect(plan.findingCount).toBe(count);
    expect(plan.verifiedQuoteCount + plan.unverifiedQuoteCount).toBe(count);
    expect(plan.ownerSignoff).toBe(false);
    expect(plan.decisionClass).toBe("AUTOMATED_SYNTHETIC_TEST_RECONCILIATION");
    expect(() => assertSyntheticSpecDecisionsPersisted(plan, 200, doc(count, "CONFIRMED"))).not.toThrow();
  });

  it.each([
    { environment: "production" },
    { environment: "development" },
    { integralUat: "0" },
    { integralUat: undefined },
    { aiMode: "deterministic-rehearsal" },
    { aiMock: "1" },
  ])("refuses synthetic approvals outside the exact disposable CI runner: %o", (change) => {
    expect(() => planSyntheticSpecReview(200, doc(2), REVIEW, { ...MODE, ...change })).toThrow(
      "G5_SYNTHETIC_TEST_REVIEW_REFUSES_NON_EPHEMERAL_CONTEXT",
    );
  });

  it("requires a real canonical readback rather than treating a missing panel as zero", () => {
    expect(() => planSyntheticSpecReview(404, null, REVIEW, MODE)).toThrow(
      "G5_SPEC_FINDINGS_READBACK_UNAVAILABLE",
    );
    expect(() => planSyntheticSpecReview(200, { review_row_id: REVIEW }, REVIEW, MODE)).toThrow(
      "G5_SPEC_FINDINGS_UNPINNED_OR_MALFORMED",
    );
  });

  it("refuses mismatched review rows and predecided or noncontiguous findings", () => {
    expect(() => planSyntheticSpecReview(200, doc(2), "different", MODE)).toThrow(
      "G5_SPEC_FINDINGS_WRONG_REVIEW_ROW",
    );
    expect(() => planSyntheticSpecReview(200, doc(2, "CONFIRMED"), REVIEW, MODE)).toThrow(
      "G5_SPEC_FINDINGS_CHANGED_OR_PREDECIDED",
    );
    const noncontiguous = doc(2);
    noncontiguous.findings[1]!.ordinal = 5;
    expect(() => planSyntheticSpecReview(200, noncontiguous, REVIEW, MODE)).toThrow(
      "G5_SPEC_FINDINGS_CHANGED_OR_PREDECIDED",
    );
  });

  it("refuses an unreviewed, parked, stale, or mismatched final ledger", () => {
    const plan = planSyntheticSpecReview(200, doc(2), REVIEW, MODE);
    for (const action of [null, "NEEDS_INFO", "DISMISSED", "CORRECTION_PROPOSED"]) {
      expect(() => assertSyntheticSpecDecisionsPersisted(plan, 200, doc(2, action))).toThrow(
        "G5_SPEC_FINDINGS_NOT_ALL_CONFIRMED_OR_CANDIDATE_CHANGED",
      );
    }
    expect(() => assertSyntheticSpecDecisionsPersisted(plan, 200, doc(3, "CONFIRMED"))).toThrow();
    expect(() =>
      assertSyntheticSpecDecisionsPersisted(plan, 200, { ...doc(2, "CONFIRMED"), artifact_hash: "b".repeat(64) }),
    ).toThrow();
    expect(() => assertSyntheticSpecDecisionsPersisted(plan, 404, null)).toThrow(
      "G5_SPEC_FINDINGS_FINAL_READBACK_UNAVAILABLE",
    );
  });
});
