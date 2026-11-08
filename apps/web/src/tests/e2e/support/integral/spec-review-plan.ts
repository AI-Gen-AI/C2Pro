/**
 * Real-AI S5 technical UAT: plan simulated test-actor decisions for the
 * synthetic, ephemeral CI database ONLY. This is NOT owner approval.
 *
 * The API's reconciliation gate is authoritative; this planner never writes
 * a decision, relaxes its rules, or evaluates the semantic accuracy of AI.
 */
export interface SyntheticReviewContext {
  environment?: string;
  integralUat?: string;
  aiMode?: string;
  aiMock?: string;
}

export interface SyntheticSpecPlan {
  ordinals: number[];
  findingCount: number;
  artifactHash: string;
  reviewRowId: string;
  verifiedQuoteCount: number;
  unverifiedQuoteCount: number;
  decisionClass: "AUTOMATED_SYNTHETIC_TEST_RECONCILIATION";
  ownerSignoff: false;
}

export function planSyntheticSpecReview(
  httpStatus: number,
  raw: unknown,
  requestedReviewRowId: string,
  context: SyntheticReviewContext,
): SyntheticSpecPlan {
  if (
    context.environment !== "test" ||
    context.integralUat !== "1" ||
    context.aiMode !== "real-ai" ||
    context.aiMock !== "0"
  ) {
    throw new Error("G5_SYNTHETIC_TEST_REVIEW_REFUSES_NON_EPHEMERAL_CONTEXT");
  }
  if (httpStatus !== 200 || !raw || typeof raw !== "object" || Array.isArray(raw)) {
    throw new Error("G5_SPEC_FINDINGS_READBACK_UNAVAILABLE");
  }
  const body = raw as Record<string, unknown>;
  if (body.review_row_id !== requestedReviewRowId || !requestedReviewRowId) {
    throw new Error("G5_SPEC_FINDINGS_WRONG_REVIEW_ROW");
  }
  if (
    typeof body.artifact_hash !== "string" ||
    !/^[a-f0-9]{64}$/.test(body.artifact_hash) ||
    !Array.isArray(body.findings) ||
    body.findings.length > 100
  ) {
    throw new Error("G5_SPEC_FINDINGS_UNPINNED_OR_MALFORMED");
  }
  const findings = body.findings as unknown[];
  let verifiedQuoteCount = 0;
  const ordinals = findings.map((entry, index) => {
    if (!entry || typeof entry !== "object" || Array.isArray(entry)) {
      throw new Error("G5_SPEC_FINDINGS_UNPINNED_OR_MALFORMED");
    }
    const item = entry as Record<string, unknown>;
    if (
      item.ordinal !== index ||
      typeof item.finding_id !== "string" ||
      !item.finding_id ||
      typeof item.source_item_id !== "string" ||
      !item.source_item_id ||
      item.current != null
    ) {
      throw new Error("G5_SPEC_FINDINGS_CHANGED_OR_PREDECIDED");
    }
    const risk = item.risk;
    if (risk && typeof risk === "object" && !Array.isArray(risk)) {
      const r = risk as Record<string, unknown>;
      if (
        r.source_quote_status === "VERIFIED" &&
        typeof r.source_quote === "string" &&
        r.source_quote.trim()
      ) {
        verifiedQuoteCount++;
      }
    }
    return index;
  });
  return {
    ordinals,
    findingCount: findings.length,
    artifactHash: body.artifact_hash,
    reviewRowId: requestedReviewRowId,
    verifiedQuoteCount,
    unverifiedQuoteCount: findings.length - verifiedQuoteCount,
    decisionClass: "AUTOMATED_SYNTHETIC_TEST_RECONCILIATION",
    ownerSignoff: false,
  };
}

export function assertSyntheticSpecDecisionsPersisted(
  plan: SyntheticSpecPlan,
  httpStatus: number,
  raw: unknown,
): void {
  if (httpStatus !== 200 || !raw || typeof raw !== "object" || Array.isArray(raw)) {
    throw new Error("G5_SPEC_FINDINGS_FINAL_READBACK_UNAVAILABLE");
  }
  const body = raw as Record<string, unknown>;
  if (
    body.review_row_id !== plan.reviewRowId ||
    body.artifact_hash !== plan.artifactHash ||
    !Array.isArray(body.findings) ||
    body.findings.length !== plan.findingCount ||
    !body.findings.every((entry: unknown, index: number) => {
      if (!entry || typeof entry !== "object" || Array.isArray(entry)) return false;
      const finding = entry as Record<string, unknown>;
      const decision = finding.current as Record<string, unknown> | null | undefined;
      return finding.ordinal === index &&
        (plan.findingCount === 0 || decision?.action === "CONFIRMED");
    })
  ) {
    throw new Error("G5_SPEC_FINDINGS_NOT_ALL_CONFIRMED_OR_CANDIDATE_CHANGED");
  }
}
