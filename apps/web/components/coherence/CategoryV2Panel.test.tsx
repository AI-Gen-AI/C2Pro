import { render, screen } from "@/src/tests/test-utils";
import { describe, expect, it } from "vitest";

import type { CoherenceV2Payload } from "@/lib/api/contracts";
import { CategoryV2Panel } from "./CategoryV2Panel";

const payload: CoherenceV2Payload = {
  project_id: "proj-v2",
  version: "coherence-v2",
  generated_at: "2026-07-11T00:00:00Z",
  global: {
    coherence_score: null,
    completeness_score: 45,
    technical_reliability_index: 92,
    status: "partial",
    score_reason: "missing active evidence",
    active_weight: 0.4,
  },
  categories: [
    {
      category: "BUDGET",
      status: "scored",
      coherence_score: 82,
      evidence_coverage: 0.75,
      technical_reliability: 0.9,
      evidence_freshness: 0.8,
      applicability_reason: "Budget evidence found",
      score_explanation: null,
      evidence_count: 4,
      missing_evidence: [],
      detected_conflicts: [
        {
          title: "Budget total mismatch",
          evidence: "Budget and contract totals differ.",
        },
      ],
      recommendation: "Review contract and budget totals.",
    },
    {
      category: "TIME",
      status: "insufficient_evidence",
      coherence_score: null,
      evidence_coverage: 0.25,
      technical_reliability: 0.8,
      evidence_freshness: 0.7,
      applicability_reason: null,
      score_explanation: null,
      evidence_count: 1,
      missing_evidence: ["baseline schedule", "critical path"],
      detected_conflicts: [],
      recommendation: "Upload an approved schedule.",
    },
  ],
};

describe("CategoryV2Panel", () => {
  it("renders backend category status, coverage, conflicts, missing evidence, and recommendations", () => {
    render(<CategoryV2Panel payload={payload} />);

    expect(screen.getByText("Evidence-aware categories")).toBeInTheDocument();
    expect(screen.getByText("Budget")).toBeInTheDocument();
    expect(screen.getByText("82")).toBeInTheDocument();
    expect(screen.getByText("Evidence coverage 75%")).toBeInTheDocument();
    expect(screen.getByText("1 detected conflict")).toBeInTheDocument();
    expect(screen.getByText("Budget total mismatch")).toBeInTheDocument();
    expect(screen.getByText("Review contract and budget totals.")).toBeInTheDocument();

    expect(screen.getByText("Time")).toBeInTheDocument();
    expect(screen.getByText("Score unavailable")).toBeInTheDocument();
    expect(screen.getByText("Evidence coverage 25%")).toBeInTheDocument();
    expect(screen.getByText("baseline schedule")).toBeInTheDocument();
    expect(screen.getByText("critical path")).toBeInTheDocument();
    expect(screen.getByText("Upload an approved schedule.")).toBeInTheDocument();
  });

  it("renders insufficient evidence without destructive styling", () => {
    render(<CategoryV2Panel payload={payload} />);

    const warningBadge = screen.getByTestId("status-badge-neutral");
    expect(warningBadge).toHaveAttribute("data-status", "insufficient_evidence");
    expect(warningBadge.className).toMatch(/gray/);
    expect(warningBadge.className).not.toMatch(/red-1|red-9/);
  });
});
