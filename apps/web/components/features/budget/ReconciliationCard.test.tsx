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
});
