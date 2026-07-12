/**
 * Test Suite ID: TASK-1487
 * Route Coverage: canonical budget route uses the backend budget endpoint
 */
import { renderWithProviders, screen } from "@/src/tests/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ProjectBudgetPage from "./page";

const useParamsMock = vi.fn();
const useBudgetMock = vi.fn();
const alertMock = vi.fn();

vi.mock("next/navigation", () => ({
  useParams: () => useParamsMock(),
}));

vi.mock("@/hooks/useBudget", () => ({
  useBudget: (...args: unknown[]) => useBudgetMock(...args),
  calculateCategoryBreakdown: () => [],
  calculateVarianceData: () => [],
}));

describe("ProjectBudgetPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.alert = alertMock;
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
});
