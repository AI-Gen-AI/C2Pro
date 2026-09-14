/**
 * PJ-01 Health evaluator: six canonical single-document categories, honest nulls.
 *
 * Mirrors the backend contracts (`health.domain.single_document_coverage`,
 * `health.domain.category_coverage`) and the P0b journey invariants, so a browser run can
 * explain exactly which promise was broken instead of failing on a generic assertion.
 */

export const CANONICAL_CATEGORIES = ["SCOPE", "BUDGET", "TIME", "TECHNICAL", "LEGAL", "QUALITY"] as const;
export type CanonicalCategory = (typeof CANONICAL_CATEGORIES)[number];

export interface CategoryAssessmentPayload {
  category: string;
  state: string;
  evidence_count?: number;
  evidence_clause_ids?: string[];
  missing_data?: string[];
  gap?: unknown;
}

/** `GET /api/v1/projects/{id}/health`, as far as PJ-01 reads it. */
export interface HealthVectorPayload {
  single_document_coverage?: { assessments?: CategoryAssessmentPayload[] | null } | null;
  single_document_evidence_granularity?: string | null;
}

export interface CategoryExpectation {
  state: "present" | "insufficient_evidence";
  evidenceCount?: number;
}

export interface HealthExpectations {
  granularity?: "clause" | "document";
  categories?: Partial<Record<CanonicalCategory, CategoryExpectation>>;
}

export type HealthViolationCode =
  | "COVERAGE_MISSING"
  | "CATEGORY_SET_MISMATCH"
  | "DUPLICATE_CATEGORY"
  | "UNKNOWN_STATE"
  | "PRESENT_WITHOUT_EVIDENCE"
  | "EVIDENCE_COUNT_MISMATCH"
  | "DUPLICATE_EVIDENCE_ID"
  | "CLAUSE_ID_NOT_UUID"
  | "INSUFFICIENT_WITH_EVIDENCE"
  | "INSUFFICIENT_WITHOUT_GAP"
  | "INSUFFICIENT_WITHOUT_MISSING_DATA"
  | "GRANULARITY_UNDISCLOSED"
  | "GRANULARITY_MISMATCH"
  | "EXPECTED_STATE_MISMATCH"
  | "EXPECTED_COUNT_MISMATCH"
  | "FABRICATED_ZERO"
  | "UNKNOWN_NOT_LABELLED";

export interface HealthViolation {
  code: HealthViolationCode;
  category?: string;
  detail: string;
}

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function evaluateHealthVector(
  vector: HealthVectorPayload,
  expectations: HealthExpectations = {},
): HealthViolation[] {
  const coverage = vector.single_document_coverage;
  if (!coverage) {
    return [
      {
        code: "COVERAGE_MISSING",
        detail: "no single-document assessment exists yet (not evaluated is not evaluated-and-empty)",
      },
    ];
  }

  const violations: HealthViolation[] = [];
  const assessments = coverage.assessments ?? [];
  const granularity = vector.single_document_evidence_granularity ?? null;

  const seen = new Map<string, number>();
  for (const assessment of assessments) seen.set(assessment.category, (seen.get(assessment.category) ?? 0) + 1);
  for (const [category, count] of seen) {
    if (count > 1) violations.push({ code: "DUPLICATE_CATEGORY", category, detail: `${category} assessed ${count} times` });
  }
  const categories = [...seen.keys()].sort();
  if (categories.join() !== [...CANONICAL_CATEGORIES].sort().join()) {
    violations.push({
      code: "CATEGORY_SET_MISMATCH",
      detail: `expected ${[...CANONICAL_CATEGORIES].join(", ")}; got ${categories.join(", ") || "(none)"}`,
    });
  }

  if (!granularity) {
    violations.push({ code: "GRANULARITY_UNDISCLOSED", detail: "evidence granularity must be disclosed, not inferred" });
  } else if (expectations.granularity && expectations.granularity !== granularity) {
    violations.push({
      code: "GRANULARITY_MISMATCH",
      detail: `expected ${expectations.granularity} granularity, got ${granularity}`,
    });
  }

  for (const assessment of assessments) {
    const { category } = assessment;
    const ids = assessment.evidence_clause_ids ?? [];
    const count = assessment.evidence_count ?? 0;

    if (new Set(ids).size !== ids.length) {
      violations.push({ code: "DUPLICATE_EVIDENCE_ID", category, detail: `${category} repeats an evidence clause id` });
    }
    if (count !== ids.length) {
      violations.push({
        code: "EVIDENCE_COUNT_MISMATCH",
        category,
        detail: `${category} evidence_count=${count} but ${ids.length} evidence ids`,
      });
    }

    if (assessment.state === "present") {
      if (ids.length === 0) {
        violations.push({ code: "PRESENT_WITHOUT_EVIDENCE", category, detail: `${category} is PRESENT without evidence` });
      }
      if (granularity === "clause") {
        for (const id of ids) {
          if (!UUID_PATTERN.test(id)) {
            violations.push({
              code: "CLAUSE_ID_NOT_UUID",
              category,
              detail: `${category}: clause granularity requires persisted clause UUIDs, got ${id}`,
            });
            break;
          }
        }
      }
    } else if (assessment.state === "insufficient_evidence") {
      if (ids.length > 0 || count > 0) {
        violations.push({ code: "INSUFFICIENT_WITH_EVIDENCE", category, detail: `${category} is unknown yet carries evidence` });
      }
      if (!assessment.gap) {
        violations.push({ code: "INSUFFICIENT_WITHOUT_GAP", category, detail: `${category} lacks an actionable gap` });
      }
      if (!assessment.missing_data?.length) {
        violations.push({
          code: "INSUFFICIENT_WITHOUT_MISSING_DATA",
          category,
          detail: `${category} does not say what evidence is missing`,
        });
      }
    } else {
      violations.push({ code: "UNKNOWN_STATE", category, detail: `${category} has unknown state ${assessment.state}` });
    }

    const expected = expectations.categories?.[category as CanonicalCategory];
    if (expected) {
      if (expected.state !== assessment.state) {
        violations.push({
          code: "EXPECTED_STATE_MISMATCH",
          category,
          detail: `${category} expected ${expected.state}, got ${assessment.state}`,
        });
      }
      if (expected.evidenceCount !== undefined && expected.evidenceCount !== ids.length) {
        violations.push({
          code: "EXPECTED_COUNT_MISMATCH",
          category,
          detail: `${category} expected ${expected.evidenceCount} evidence clauses, got ${ids.length}`,
        });
      }
    }
  }

  return violations;
}

const FABRICATED_ZERO = /(^|[^\d.])0(?:\.0+)?\s*%|\bscore:?\s*0(?:\.0+)?\b/i;
const UNKNOWN_LABEL = /unknown\s*\/\s*insufficient evidence/i;

/** Judge the text a user reads on one Health category tile. */
export function evaluateHealthTileText(category: string, state: string, text: string): HealthViolation[] {
  if (state !== "insufficient_evidence") return [];
  if (FABRICATED_ZERO.test(text)) {
    return [{ code: "FABRICATED_ZERO", category, detail: `${category} renders an unknown category as zero: "${text}"` }];
  }
  if (!UNKNOWN_LABEL.test(text)) {
    return [
      {
        code: "UNKNOWN_NOT_LABELLED",
        category,
        detail: `${category} lacks evidence but does not say "Unknown / Insufficient evidence"`,
      },
    ];
  }
  return [];
}
