/**
 * Test Suite ID: TS-UD-COH-V1-09
 * Coverage: Coherence v1 score-version UX and audit-incomplete banner
 */
import { render, screen } from "@/src/tests/test-utils";
import { describe, expect, it, vi } from "vitest";

import { CoherenceClient } from "./CoherenceClient";

vi.mock("@/components/coherence/CoherenceGauge", () => ({
  CoherenceGauge: ({ score }: { score: number }) => <div>Gauge {score}</div>,
}));

vi.mock("@/components/coherence/BreakdownChart", () => ({
  BreakdownChart: () => <div>Breakdown chart</div>,
}));

vi.mock("@/components/coherence/RadarView", () => ({
  RadarView: () => <div>Radar chart</div>,
}));

vi.mock("@/components/coherence/AlertsDistribution", () => ({
  AlertsDistribution: () => <div>Alerts chart</div>,
}));

vi.mock("@/components/coherence/CategoryDetail", () => ({
  CategoryDetail: () => <div>Category detail</div>,
}));

vi.mock("@/components/coherence/ScoreCard", () => ({
  ScoreCard: ({ category, score }: { category: string; score: number }) => (
    <button type="button">
      {category} {score}
    </button>
  ),
}));

describe("CoherenceClient v1 UX", () => {
  it("renders the v1 announcement banner and score-version badge for scored audits", () => {
    render(
      <CoherenceClient
        summary={{
          project_id: "proj-1",
          tenant_id: "tenant-1",
          coherence_score: 82,
          global_score: 82,
          sub_scores: { BUDGET: 80 },
          weights_used: { BUDGET: 1 },
          alert_count: 2,
          document_count: 3,
          methodology_version: "v1",
          score_version: "coherence-v1",
          score_reason: null,
          score_missing_dimensions: [],
          last_updated: "2026-05-01T00:00:00Z",
        }}
      />,
    );

    expect(screen.getByText(/coherence score v1 is active/i)).toBeInTheDocument();
    expect(screen.getByText("(v1)")).toBeInTheDocument();
    expect(screen.getByText(/gauge 82/i)).toBeInTheDocument();
  });

  it("withholds the gauge and shows an AUDIT_INCOMPLETE banner when score is null", () => {
    render(
      <CoherenceClient
        summary={{
          project_id: "proj-1",
          tenant_id: "tenant-1",
          coherence_score: null,
          global_score: null,
          sub_scores: {},
          weights_used: {},
          alert_count: 1,
          document_count: 1,
          methodology_version: "v1",
          score_version: "coherence-v1",
          score_reason: "insufficient_evidence",
          score_missing_dimensions: ["schedule", "budget"],
          last_updated: "2026-05-01T00:00:00Z",
        }}
      />,
    );

    expect(screen.getByText(/supply missing dimensions to unlock full coherence score/i)).toBeInTheDocument();
    expect(screen.getByText(/schedule, budget/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /upload schedule and budget/i })).toHaveAttribute(
      "href",
      "/projects/proj-1/documents",
    );
    expect(screen.queryByText(/gauge/i)).not.toBeInTheDocument();
  });
});
