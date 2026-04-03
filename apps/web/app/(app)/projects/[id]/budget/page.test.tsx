/**
 * Test Suite ID: TASK-1487
 * Route Coverage: canonical budget route uses the backend budget endpoint
 */
import { renderWithProviders, screen } from "@/src/tests/test-utils";
import { describe, expect, it, vi } from "vitest";
import ProjectBudgetPage from "./page";

const useParamsMock = vi.fn();
const useProjectBudgetMock = vi.fn();

vi.mock("next/navigation", () => ({
  useParams: () => useParamsMock(),
}));

vi.mock("@/lib/api/generated/projects/projects", () => ({
  useGetProjectBudgetApiV1ProjectsProjectIdBudgetGet: (...args: unknown[]) =>
    useProjectBudgetMock(...args),
}));

describe("ProjectBudgetPage", () => {
  it("renders budget data from the backend budget endpoint instead of local hardcoded values", () => {
    useParamsMock.mockReturnValue({ id: "proj-real-budget" });
    useProjectBudgetMock.mockReturnValue({
      data: {
        total_budget: 3200000,
        spent_amount: 1760000,
        utilization_percentage: 55,
        variance_status: "Watch",
      },
      isLoading: false,
      error: null,
    });

    renderWithProviders(<ProjectBudgetPage />);

    expect(useProjectBudgetMock).toHaveBeenCalledWith(
      "proj-real-budget",
      undefined,
    );
    expect(screen.getByTestId("budget-page")).toBeInTheDocument();
    expect(screen.getByTestId("total-budget")).toHaveTextContent("€3,200,000");
    expect(screen.getByTestId("spent-amount")).toHaveTextContent("€1,760,000");
    expect(screen.getByTestId("budget-utilization")).toHaveTextContent("55%");
    expect(screen.getByTestId("budget-variance")).toHaveTextContent("Watch");
    expect(screen.getByTestId("budget-chart")).toHaveTextContent("€1,440,000");
  });
});
