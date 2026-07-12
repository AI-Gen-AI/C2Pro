/**
 * Test Suite ID: TASK-1487
 * Route Coverage: canonical budget route uses the backend budget endpoint
 */
import { renderWithProviders, screen } from "@/src/tests/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ProjectBudgetPage from "./page";

const useParamsMock = vi.fn();
const useBudgetMock = vi.fn();
const getDashboardSummaryMock = vi.fn();
const alertMock = vi.fn();

vi.mock("next/navigation", () => ({
  useParams: () => useParamsMock(),
}));

vi.mock("@/hooks/useBudget", () => ({
  useBudget: (...args: unknown[]) => useBudgetMock(...args),
  calculateCategoryBreakdown: () => [],
  calculateVarianceData: () => [],
}));

vi.mock("@/lib/api/services/dashboard", () => ({
  getDashboardSummary: (...args: unknown[]) => getDashboardSummaryMock(...args),
}));

describe("ProjectBudgetPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.alert = alertMock;
    getDashboardSummaryMock.mockResolvedValue({
      project_id: "proj-real-budget",
      tenant_id: "tenant-1",
      coherence_score: null,
      global_score: null,
      sub_scores: {},
      weights_used: {},
      alert_count: 0,
      document_count: 0,
      methodology_version: "coherence-v2",
      last_updated: null,
      categories_v2: null,
    });
  });

  it("renders budget data from the backend budget endpoint instead of local hardcoded values", () => {
    useParamsMock.mockReturnValue({ id: "proj-real-budget" });
    useBudgetMock.mockReturnValue({
      budget: {
        total_budget: 3200000,
        spent_amount: 1760000,
        utilization_percentage: 55,
        variance_status: "Watch",
      },
      isLoading: false,
      isError: false,
      error: null,
      createItem: vi.fn(),
      updateItem: vi.fn(),
      deleteItem: vi.fn(),
      selectedItem: null,
      setSelectedItem: vi.fn(),
    });

    renderWithProviders(<ProjectBudgetPage />);

    expect(useBudgetMock).toHaveBeenCalledWith({ projectId: "proj-real-budget" });
    expect(screen.getByTestId("budget-page")).toBeInTheDocument();
    expect(screen.getByTestId("total-budget")).toHaveTextContent("€3,200,000");
    expect(screen.getByTestId("spent-amount")).toHaveTextContent("€1,760,000");
    expect(screen.getByTestId("budget-utilization")).toHaveTextContent("55%");
    expect(screen.getByTestId("budget-variance")).toHaveTextContent("Watch");
    expect(screen.getByRole("link", { name: /open audit report/i })).toHaveAttribute(
      "href",
      "/projects/proj-real-budget/report",
    );
    expect(screen.queryByRole("button", { name: /export pdf/i })).not.toBeInTheDocument();
    expect(alertMock).not.toHaveBeenCalled();
  });

  it("renders budget reconciliation only from dashboard category payload totals", async () => {
    useParamsMock.mockReturnValue({ id: "proj-real-budget" });
    useBudgetMock.mockReturnValue({
      budget: {
        total_budget: 3200000,
        spent_amount: 1760000,
        utilization_percentage: 55,
        variance_status: "Watch",
        currency: "EUR",
      },
      isLoading: false,
      isError: false,
      error: null,
      createItem: vi.fn(),
      updateItem: vi.fn(),
      deleteItem: vi.fn(),
      selectedItem: null,
      setSelectedItem: vi.fn(),
    });
    getDashboardSummaryMock.mockResolvedValue({
      project_id: "proj-real-budget",
      tenant_id: "tenant-1",
      coherence_score: null,
      global_score: null,
      sub_scores: {},
      weights_used: {},
      alert_count: 0,
      document_count: 0,
      methodology_version: "coherence-v2",
      last_updated: null,
      categories_v2: {
        project_id: "proj-real-budget",
        version: "coherence-v2",
        generated_at: "2026-07-12T00:00:00Z",
        global: {
          coherence_score: null,
          completeness_score: 50,
          technical_reliability_index: 90,
          status: "partial",
          score_reason: null,
          active_weight: 0.5,
        },
        categories: [
          {
            category: "BUDGET",
            status: "scored",
            coherence_score: 78,
            evidence_coverage: 0.8,
            technical_reliability: 0.92,
            evidence_freshness: 0.9,
            applicability_reason: "Budget evidence found",
            score_explanation: null,
            detected_conflicts: [
              {
                rule_id: "DET-BUD-SUM",
                raw_data: {
                  stated_total: 1500,
                  items_sum: 1200,
                  contract_total: 1600,
                  deviation_pct: 20,
                },
              },
            ],
            recommendation: "Review budget totals.",
          },
        ],
      },
    });

    renderWithProviders(<ProjectBudgetPage />);

    expect(await screen.findByText("Budget reconciliation")).toBeInTheDocument();
    expect(getDashboardSummaryMock).toHaveBeenCalledWith("proj-real-budget");
    expect(screen.getByText("20.0% delta")).toBeInTheDocument();
    expect(screen.getByText("1,200")).toBeInTheDocument();
  });
});
