/**
 * Test Suite ID: TASK-FRT-193
 */
import { render, screen } from "@/src/tests/test-utils";
import { describe, expect, it } from "vitest";

import type { CategoryV2 } from "@/lib/api/contracts";
import { ReconciliationCard } from "./ReconciliationCard";

const baseBudgetCategory: CategoryV2 = {
  category: "BUDGET",
  status: "scored",
  coherence_score: 78,
  evidence_coverage: 0.8,
  technical_reliability: 0.92,
  evidence_freshness: 0.9,
  applicability_reason: "Budget evidence found",
  score_explanation: null,
  detected_conflicts: [],
  recommendation: "Review budget totals.",
};

describe("ReconciliationCard", () => {
  it("renders stated, computed, contract, and delta values from a structured budget payload", () => {
    render(
      <ReconciliationCard
        category={{
          ...baseBudgetCategory,
          detected_conflicts: [
            {
              rule_id: "DET-BUD-SUM",
              finding_id: "finding-budget-1",
              raw_data: {
                stated_total: 1500,
                items_sum: 1200,
                contract_total: 1600,
                deviation_pct: 20,
              },
            },
          ],
        }}
      />,
    );

    expect(screen.getByText("Budget reconciliation")).toBeInTheDocument();
    expect(screen.getByText("Stated total")).toBeInTheDocument();
    expect(screen.getByText("1,500")).toBeInTheDocument();
    expect(screen.getByText("Computed from line items")).toBeInTheDocument();
    expect(screen.getByText("1,200")).toBeInTheDocument();
    expect(screen.getByText("Contract base")).toBeInTheDocument();
    expect(screen.getByText("1,600")).toBeInTheDocument();
    expect(screen.getByText("20.0% delta")).toBeInTheDocument();
    expect(screen.getByText("Source: DET-BUD-SUM")).toBeInTheDocument();
  });

  it("renders no reconciliation block when the category lacks all required totals", () => {
    render(<ReconciliationCard category={baseBudgetCategory} />);

    expect(screen.queryByText("Budget reconciliation")).not.toBeInTheDocument();
    expect(screen.queryByText("1,200")).not.toBeInTheDocument();
    expect(screen.queryByText("1,500")).not.toBeInTheDocument();
  });

  // #860: structured budget lines are unavailable -> say so, never show a clean result.
  const unavailableBudgetCategory: CategoryV2 = {
    ...baseBudgetCategory,
    status: "insufficient_evidence",
    coherence_score: null,
    rationale: "structured_budget_source_unavailable",
    calculation_metadata: {
      assessment_state: "unassessed",
      assessment_reason: "structured_budget_source_unavailable",
    },
  };

  it("states that budget line reconciliation is unavailable pending a structured budget model", () => {
    render(<ReconciliationCard category={unavailableBudgetCategory} />);

    expect(screen.getByTestId("budget-reconciliation-unavailable")).toBeInTheDocument();
    expect(screen.getByText("Budget line reconciliation unavailable")).toBeInTheDocument();
    expect(screen.getByText(/not evaluated/i)).toBeInTheDocument();
    expect(screen.getByText(/pending a structured budget model/i)).toBeInTheDocument();
    expect(screen.queryByText("Computed from line items")).not.toBeInTheDocument();
  });

  it("never assembles reconciliation figures from conflict totals while lines are unavailable", () => {
    render(
      <ReconciliationCard
        category={{
          ...unavailableBudgetCategory,
          detected_conflicts: [
            { rule_id: "DET-BUD-SUM", compared_values: { items_sum: 1200, contract_total: 1600 } },
            { rule_id: "DET-BUD-INTERNAL", compared_values: { items_sum: 1200, stated_total: 1500 } },
          ],
        }}
      />,
    );

    expect(screen.getByTestId("budget-reconciliation-unavailable")).toBeInTheDocument();
    expect(screen.queryByText("Computed from line items")).not.toBeInTheDocument();
    expect(screen.queryByText("1,200")).not.toBeInTheDocument();
    expect(screen.queryByText(/delta/i)).not.toBeInTheDocument();
  });
});
