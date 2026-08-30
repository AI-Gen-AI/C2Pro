/**
 * P0b-L4-5 — user-visible single-document Health surface.
 *
 * RED-first acceptance for the twelve required proofs. Every fixture below is built
 * from the GENERATED #581 contract types (HealthVector / SingleDocumentCoverage /
 * CategoryAssessment / EvidenceGranularity), never a hand-rolled parallel shape — if
 * the API contract changes, these fixtures stop compiling rather than drifting.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithProviders, screen, within } from "@/src/tests/test-utils";
import {
  CategoryCoverageState,
  CoherenceCategory,
  EvidenceGranularity,
  EvidenceTier,
  HealthBand,
  HealthDimension,
  type CategoryAssessment,
  type HealthSignal,
  type HealthVector,
  type SingleDocumentCoverage,
} from "@/lib/api/generated/models";

import {
  COHERENCE_SUBSCORE_EVIDENCE_REF,
  SingleDocumentHealth,
} from "./SingleDocumentHealth";

const healthQueryMock = vi.fn();

vi.mock("@/lib/api/generated/project-health/project-health", () => ({
  useGetProjectHealthApiV1ProjectsProjectIdHealthGet: (...args: unknown[]) =>
    healthQueryMock(...args),
}));

const BUDGET_CLAUSE = "aaaaaaaa-0000-4000-8000-000000000001";
const LEGAL_CLAUSE = "aaaaaaaa-0000-4000-8000-000000000002";

function present(
  category: CoherenceCategory,
  clauseId: string,
): CategoryAssessment {
  return {
    category,
    state: CategoryCoverageState.present,
    evidence_count: 1,
    evidence_clause_ids: [clauseId],
    findings: [],
    missing_data: [],
    gap: null,
  };
}

function insufficient(
  category: CoherenceCategory,
  action: string,
  missing: string[],
): CategoryAssessment {
  return {
    category,
    state: CategoryCoverageState.insufficient_evidence,
    evidence_count: 0,
    evidence_clause_ids: [],
    findings: [],
    missing_data: missing,
    gap: { category, action },
  };
}

const COVERAGE: SingleDocumentCoverage = {
  assessments: [
    insufficient(CoherenceCategory.SCOPE, "Upload the contract scope / statement of work to assess SCOPE.", ["statement of work"]),
    present(CoherenceCategory.BUDGET, BUDGET_CLAUSE),
    insufficient(CoherenceCategory.QUALITY, "Upload the quality plan / acceptance criteria to assess QUALITY.", ["acceptance criteria"]),
    insufficient(CoherenceCategory.TECHNICAL, "Upload the technical specifications to assess TECHNICAL.", ["technical specifications"]),
    present(CoherenceCategory.LEGAL, LEGAL_CLAUSE),
    insufficient(CoherenceCategory.TIME, "Upload the project schedule to assess TIME.", ["project schedule"]),
  ],
  cross_findings: [],
};

/**
 * ``coherence_subscore`` is NOT a HealthVector field — it is an input to the contract
 * scorer, which signals the outcome by attaching the ``project-coherence-subscore``
 * evidence ref to the CONTRACT dimension only when a subscore existed. These fixtures
 * therefore model the real contract, not a convenient invented field.
 */
function contractDimension(withCoherence: boolean): HealthSignal {
  return {
    dimension: HealthDimension.contract,
    band: HealthBand.unknown,
    confidence: 0.5,
    score: null,
    evidence: withCoherence
      ? [
          {
            ref_id: COHERENCE_SUBSCORE_EVIDENCE_REF,
            source: "project_coherence",
            tier: EvidenceTier.weak,
            locator: "overall_score",
          },
        ]
      : [],
    missing_data: withCoherence ? [] : ["coherence subscore unavailable"],
  } as HealthSignal;
}

function vector(overrides: Partial<HealthVector> = {}): HealthVector {
  return {
    project_id: "proj-1",
    tenant_id: "tenant-1",
    dimensions: [contractDimension(false)],
    single_document_coverage: COVERAGE,
    single_document_evidence_granularity: EvidenceGranularity.clause,
    ...overrides,
  } as HealthVector;
}

function resolved(data: HealthVector) {
  return { data, isLoading: false, isError: false, error: null };
}

function renderHealth() {
  return renderWithProviders(<SingleDocumentHealth projectId="proj-1" />);
}

beforeEach(() => {
  healthQueryMock.mockReset();
});

// ── 1 — six-category view renders from the generated HealthVector type ─────────

describe("1 — six-category view from the generated contract", () => {
  it("renders exactly the six canonical categories", () => {
    healthQueryMock.mockReturnValue(resolved(vector()));

    renderHealth();

    for (const category of Object.values(CoherenceCategory)) {
      expect(screen.getByTestId(`health-category-${category}`)).toBeInTheDocument();
    }
    expect(screen.getAllByTestId(/^health-category-/)).toHaveLength(6);
  });

  it("renders a category the payload omits as insufficient rather than dropping it", () => {
    // A category missing from the payload is NOT evidence of coverage. It must still
    // appear, as unknown — silently rendering five tiles would hide a whole dimension.
    const partial: SingleDocumentCoverage = {
      assessments: COVERAGE.assessments!.filter(
        (a) => a.category !== CoherenceCategory.QUALITY,
      ),
    };
    healthQueryMock.mockReturnValue(
      resolved(vector({ single_document_coverage: partial })),
    );

    renderHealth();

    const quality = screen.getByTestId(`health-category-${CoherenceCategory.QUALITY}`);
    expect(within(quality).getByText(/insufficient evidence/i)).toBeInTheDocument();
  });
});

// ── 2 — PRESENT renders evidence and no gap ───────────────────────────────────

describe("2 — PRESENT category", () => {
  it("shows its evidence count and no missing-evidence gap", () => {
    healthQueryMock.mockReturnValue(resolved(vector()));

    renderHealth();

    const budget = screen.getByTestId(`health-category-${CoherenceCategory.BUDGET}`);
    expect(within(budget).getByTestId("health-evidence-count")).toHaveTextContent("1");
    expect(within(budget).queryByTestId("health-gap")).not.toBeInTheDocument();
  });
});

// ── 3 — INSUFFICIENT renders Unknown + missing_data + actionable gap ──────────

describe("3 — INSUFFICIENT category", () => {
  it("renders 'Unknown / Insufficient evidence', missing_data and the actionable gap", () => {
    healthQueryMock.mockReturnValue(resolved(vector()));

    renderHealth();

    const scope = screen.getByTestId(`health-category-${CoherenceCategory.SCOPE}`);
    expect(within(scope).getByText(/unknown/i)).toBeInTheDocument();
    expect(within(scope).getByText(/insufficient evidence/i)).toBeInTheDocument();
    expect(within(scope).getByTestId("health-missing-data")).toHaveTextContent(
      "statement of work",
    );
    expect(within(scope).getByTestId("health-gap")).toHaveTextContent(
      "Upload the contract scope / statement of work to assess SCOPE.",
    );
  });
});

// ── 2b — findings render per category, independent of coverage state ─────────

describe("2b — per-category findings", () => {
  it("renders a category's own findings, for PRESENT and INSUFFICIENT alike", () => {
    // findings are independent of coverage state: an issue can exist whether or not
    // the category is evidenced, so both cases must surface them.
    const withFindings: SingleDocumentCoverage = {
      assessments: [
        {
          ...present(CoherenceCategory.BUDGET, BUDGET_CLAUSE),
          findings: [
            {
              rule_id: "BUDGET-UNPRICED-SCOPE",
              clause_id: BUDGET_CLAUSE,
              impact_score: 0.6,
              evidence_summary: "Budget omits a priced line for the stated scope.",
            },
          ],
        },
        {
          ...insufficient(CoherenceCategory.TIME, "Upload the project schedule to assess TIME.", ["project schedule"]),
          findings: [
            {
              rule_id: "TIME-NO-MILESTONES",
              clause_id: LEGAL_CLAUSE,
              impact_score: 0.4,
            },
          ],
        },
      ],
    };
    healthQueryMock.mockReturnValue(
      resolved(vector({ single_document_coverage: withFindings })),
    );

    renderHealth();

    const budget = screen.getByTestId(`health-category-${CoherenceCategory.BUDGET}`);
    expect(within(budget).getByTestId("health-findings")).toHaveTextContent(
      "Budget omits a priced line for the stated scope.",
    );

    // A finding with no summary still shows something identifiable, never a blank row.
    const time = screen.getByTestId(`health-category-${CoherenceCategory.TIME}`);
    expect(within(time).getByTestId("health-findings")).toHaveTextContent(
      "TIME-NO-MILESTONES",
    );
  });

  it("omits the findings list for a category with no findings", () => {
    healthQueryMock.mockReturnValue(resolved(vector()));

    renderHealth();

    const budget = screen.getByTestId(`health-category-${CoherenceCategory.BUDGET}`);
    expect(within(budget).queryByTestId("health-findings")).not.toBeInTheDocument();
  });
});

// ── 4 — unknown never renders as 0% ───────────────────────────────────────────

describe("4 — honest null", () => {
  it("never renders 0% or a zero score for an unknown category", () => {
    healthQueryMock.mockReturnValue(resolved(vector()));

    const { container } = renderHealth();

    expect(container.textContent).not.toMatch(/0\s*%/);
    const scope = screen.getByTestId(`health-category-${CoherenceCategory.SCOPE}`);
    // The evidence count is a count, not a score, and must not be dressed as one.
    expect(within(scope).queryByRole("progressbar")).not.toBeInTheDocument();
    expect(scope.textContent).not.toMatch(/0\s*%/);
  });

  it("does not render a percentage anywhere on the surface", () => {
    healthQueryMock.mockReturnValue(resolved(vector()));

    const { container } = renderHealth();

    expect(container.textContent).not.toMatch(/%/);
  });
});

// ── 5 — clause UUID evidence is surfaced traceably ────────────────────────────

describe("5 — evidence traceability", () => {
  it("surfaces the persisted clause UUIDs for a PRESENT category", () => {
    healthQueryMock.mockReturnValue(resolved(vector()));

    renderHealth();

    const budget = screen.getByTestId(`health-category-${CoherenceCategory.BUDGET}`);
    expect(within(budget).getByTestId("health-evidence-ids")).toHaveTextContent(
      BUDGET_CLAUSE,
    );
    const legal = screen.getByTestId(`health-category-${CoherenceCategory.LEGAL}`);
    expect(within(legal).getByTestId("health-evidence-ids")).toHaveTextContent(
      LEGAL_CLAUSE,
    );
  });
});

// ── 6 — document granularity is visibly distinguished from clause ────────────

describe("6 — evidence-granularity disclosure", () => {
  it("labels clause granularity as clause-level", () => {
    healthQueryMock.mockReturnValue(resolved(vector()));

    renderHealth();

    const disclosure = screen.getByTestId("health-granularity");
    expect(disclosure).toHaveTextContent(/clause-level/i);
    expect(disclosure).not.toHaveTextContent(/whole[- ]document/i);
  });

  it("discloses document granularity as degraded whole-document evidence", () => {
    healthQueryMock.mockReturnValue(
      resolved(
        vector({
          single_document_evidence_granularity: EvidenceGranularity.document,
        }),
      ),
    );

    renderHealth();

    const disclosure = screen.getByTestId("health-granularity");
    expect(disclosure).toHaveTextContent(/whole[- ]document/i);
    // Must never imply clause-level precision when granularity is document.
    expect(disclosure).not.toHaveTextContent(/clause-level/i);
  });

  it("does not claim any granularity when the API reports none", () => {
    healthQueryMock.mockReturnValue(
      resolved(vector({ single_document_evidence_granularity: null })),
    );

    renderHealth();

    const disclosure = screen.getByTestId("health-granularity");
    expect(disclosure).not.toHaveTextContent(/clause-level/i);
    expect(disclosure).not.toHaveTextContent(/whole[- ]document/i);
  });
});

// ── 7 — CROSS findings stay separate ─────────────────────────────────────────

describe("7 — CROSS findings", () => {
  it("renders CROSS findings in their own region, not inside a category", () => {
    healthQueryMock.mockReturnValue(
      resolved(
        vector({
          single_document_coverage: {
            ...COVERAGE,
            cross_findings: [
              {
                rule_id: "CROSS-BUDGET-SCOPE",
                clause_id: `${BUDGET_CLAUSE}|${LEGAL_CLAUSE}`,
                impact_score: 0.7,
                evidence_summary: "Budget line has no matching scope item.",
              },
            ],
          } as SingleDocumentCoverage,
        }),
      ),
    );

    renderHealth();

    const cross = screen.getByTestId("health-cross-findings");
    expect(within(cross).getByText(/budget line has no matching scope item/i)).toBeInTheDocument();

    // And it is NOT forced into either of the categories it spans.
    for (const category of Object.values(CoherenceCategory)) {
      const tile = screen.getByTestId(`health-category-${category}`);
      expect(tile.textContent).not.toMatch(/budget line has no matching scope item/i);
    }
  });

  it("omits the CROSS region entirely when there are no CROSS findings", () => {
    healthQueryMock.mockReturnValue(resolved(vector()));

    renderHealth();

    expect(screen.queryByTestId("health-cross-findings")).not.toBeInTheDocument();
  });
});

// ── 8 — coherence_subscore null suppresses the single-doc Coherence score ─────

describe("8 — Coherence suppression for one document", () => {
  it("shows no Coherence score and explains the >=2 document requirement", () => {
    healthQueryMock.mockReturnValue(resolved(vector()));

    renderHealth();

    expect(screen.queryByTestId("health-coherence-score")).not.toBeInTheDocument();
    expect(screen.getByTestId("health-coherence-note")).toHaveTextContent(
      /two|second|2 /i,
    );
  });

  it("never substitutes zero for an unavailable coherence subscore", () => {
    healthQueryMock.mockReturnValue(resolved(vector()));

    const note = renderHealth().container.querySelector(
      '[data-testid="health-coherence-note"]',
    );

    expect(note?.textContent).not.toMatch(/\b0\b/);
  });

  it("drops the note once a coherence subscore is actually incorporated", () => {
    // Positive evidence, not an absent field: the CONTRACT dimension carries the
    // project-coherence-subscore evidence ref only when a subscore existed.
    healthQueryMock.mockReturnValue(
      resolved(vector({ dimensions: [contractDimension(true)] })),
    );

    renderHealth();

    expect(screen.queryByTestId("health-coherence-note")).not.toBeInTheDocument();
  });
});

// ── 9 — loading / error / 404 states are explicit ────────────────────────────

describe("9 — loading, error and not-found states", () => {
  it("renders an explicit loading state", () => {
    healthQueryMock.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
      error: null,
    });

    renderHealth();

    expect(screen.getByTestId("health-loading")).toBeInTheDocument();
    expect(screen.queryByTestId("health-error")).not.toBeInTheDocument();
  });

  it("renders an explicit error state, never an empty success", () => {
    healthQueryMock.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: { response: { status: 500 } },
    });

    renderHealth();

    expect(screen.getByTestId("health-error")).toBeInTheDocument();
    expect(screen.queryAllByTestId(/^health-category-/)).toHaveLength(0);
  });

  it("distinguishes 404 (project not found or not yours) from a generic failure", () => {
    healthQueryMock.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: { response: { status: 404 } },
    });

    renderHealth();

    expect(screen.getByTestId("health-not-found")).toBeInTheDocument();
    expect(screen.queryByTestId("health-error")).not.toBeInTheDocument();
  });

  it("treats an absent assessment as not-yet-evaluated, never as evaluated-empty", () => {
    healthQueryMock.mockReturnValue(
      resolved(
        vector({
          single_document_coverage: null,
          single_document_evidence_granularity: null,
        }),
      ),
    );

    renderHealth();

    expect(screen.getByTestId("health-unavailable")).toBeInTheDocument();
    expect(screen.queryAllByTestId(/^health-category-/)).toHaveLength(0);
  });
});

// ── 10 — the query uses only the generated #581 client ───────────────────────

describe("10 — generated client only", () => {
  it("calls the generated project-health hook with the project id", () => {
    healthQueryMock.mockReturnValue(resolved(vector()));

    renderHealth();

    expect(healthQueryMock).toHaveBeenCalled();
    expect(healthQueryMock.mock.calls[0][0]).toBe("proj-1");
  });
});

// ── 12 — accessibility: meaning is not carried by color alone ────────────────

describe("12 — accessibility", () => {
  it("gives every category a textual state, not just a color", () => {
    healthQueryMock.mockReturnValue(resolved(vector()));

    renderHealth();

    for (const category of Object.values(CoherenceCategory)) {
      const tile = screen.getByTestId(`health-category-${category}`);
      const state = within(tile).getByTestId("health-state");
      expect(state.textContent?.trim()).not.toHaveLength(0);
    }
  });

  it("exposes the gap as text, so it is not conveyed by an icon or color alone", () => {
    healthQueryMock.mockReturnValue(resolved(vector()));

    renderHealth();

    const scope = screen.getByTestId(`health-category-${CoherenceCategory.SCOPE}`);
    const gap = within(scope).getByTestId("health-gap");
    expect(gap.textContent?.trim().length).toBeGreaterThan(0);
  });

  it("names the region so assistive tech can reach it", () => {
    healthQueryMock.mockReturnValue(resolved(vector()));

    renderHealth();

    expect(screen.getByRole("region", { name: /health/i })).toBeInTheDocument();
  });
});
