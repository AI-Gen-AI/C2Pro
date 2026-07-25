/**
 * Test Suite ID: TS-QA-337-BUDGET-PAGE-BRANCH-COV
 * Branch coverage tests for budget page component
 */
import { renderWithProviders, screen, fireEvent, waitFor } from "@/src/tests/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import ProjectBudgetPage from "./page";

const useParamsMock = vi.fn();
const useBudgetMock = vi.fn();
const getDashboardSummaryMock = vi.fn();

vi.mock("next/navigation", () => ({
  useParams: () => useParamsMock(),
}));

vi.mock("@/hooks/useBudget", async () => {
  const actual = await vi.importActual<typeof import("@/hooks/useBudget")>("@/hooks/useBudget");
  return {
    useBudget: (...args: unknown[]) => useBudgetMock(...args),
    calculateCategoryBreakdown: actual.calculateCategoryBreakdown,
    calculateVarianceData: actual.calculateVarianceData,
  };
});

vi.mock("@/lib/api/services/dashboard", () => ({
  getDashboardSummary: (...args: unknown[]) => getDashboardSummaryMock(...args),
}));

const defaultBudgetMock = {
  budget: {
    total_budget: 100000,
    spent_amount: 40000,
    utilization_percentage: 40,
    variance_status: "On Track",
    currency: "EUR",
    items: [],
  },
  isLoading: false,
  isError: false,
  error: null,
  createItem: vi.fn(),
  updateItem: vi.fn(),
  deleteItem: vi.fn(),
  selectedItem: null,
  setSelectedItem: vi.fn(),
};

describe("ProjectBudgetPage branch coverage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useParamsMock.mockReturnValue({ id: "proj-budget" });
    getDashboardSummaryMock.mockResolvedValue({
      project_id: "proj-budget",
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

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders loading spinner when isLoading is true", () => {
    useBudgetMock.mockReturnValue({
      ...defaultBudgetMock,
      budget: null,
      isLoading: true,
    });

    const { container } = renderWithProviders(<ProjectBudgetPage />);
    expect(container.querySelector(".animate-spin")).toBeInTheDocument();
  });

  it("renders error message when isError is true with Error instance", () => {
    useBudgetMock.mockReturnValue({
      ...defaultBudgetMock,
      budget: null,
      isError: true,
      error: new Error("Network timeout"),
    });

    renderWithProviders(<ProjectBudgetPage />);
    expect(screen.getByText("Network timeout")).toBeInTheDocument();
  });

  it("renders fallback error when error is not an Error instance", () => {
    useBudgetMock.mockReturnValue({
      ...defaultBudgetMock,
      budget: null,
      isError: true,
      error: "string error",
    });

    renderWithProviders(<ProjectBudgetPage />);
    expect(screen.getByText("Failed to load budget")).toBeInTheDocument();
  });

  it("renders empty state when no budget items", () => {
    useBudgetMock.mockReturnValue({
      ...defaultBudgetMock,
    });

    renderWithProviders(<ProjectBudgetPage />);
    expect(screen.getByText(/no budget items yet/i)).toBeInTheDocument();
  });

  it("renders budget items table with items", () => {
    useBudgetMock.mockReturnValue({
      ...defaultBudgetMock,
      budget: {
        ...defaultBudgetMock.budget,
        items: [
          {
            id: "item-1",
            name: "Concrete",
            category: "materials",
            amount: 50000,
            actualAmount: 45000,
            variance: 5000,
            status: "approved",
          },
          {
            id: "item-2",
            name: "Labor",
            category: "labor",
            amount: 30000,
            actualAmount: null,
            variance: null,
            status: "planned",
          },
        ],
      },
    });

    renderWithProviders(<ProjectBudgetPage />);
    expect(screen.getAllByText("Concrete").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Labor").length).toBeGreaterThanOrEqual(1);
  });

  it("export CSV button exists and is clickable", () => {
    useBudgetMock.mockReturnValue({
      ...defaultBudgetMock,
      budget: {
        ...defaultBudgetMock.budget,
        items: [
          {
            id: "item-1",
            name: "Concrete",
            category: "materials",
            amount: 50000,
            actualAmount: 45000,
            variance: 5000,
            status: "approved",
          },
        ],
      },
    });

    renderWithProviders(<ProjectBudgetPage />);
    expect(screen.getByRole("button", { name: /export csv/i })).toBeInTheDocument();
  });

  it("opens create modal and shows form", async () => {
    useBudgetMock.mockReturnValue({
      ...defaultBudgetMock,
      createItem: vi.fn().mockResolvedValue(undefined),
    });

    renderWithProviders(<ProjectBudgetPage />);
    fireEvent.click(screen.getByRole("button", { name: /add item/i }));

    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });
    expect(screen.getByText("Create")).toBeInTheDocument();
  });

  it("calls createItem on Create button click", async () => {
    const createMock = vi.fn().mockResolvedValue(undefined);
    useBudgetMock.mockReturnValue({
      ...defaultBudgetMock,
      createItem: createMock,
    });

    renderWithProviders(<ProjectBudgetPage />);
    fireEvent.click(screen.getByRole("button", { name: /add item/i }));
    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText("Create"));

    await waitFor(() => {
      expect(createMock).toHaveBeenCalled();
    });
  });

  it("calls setSelectedItem when handleEdit is triggered via item row", async () => {
    const setSelectedMock = vi.fn();
    useBudgetMock.mockReturnValue({
      ...defaultBudgetMock,
      budget: {
        ...defaultBudgetMock.budget,
        items: [
          {
            id: "item-1",
            name: "Concrete",
            category: "materials",
            amount: 50000,
            actualAmount: 45000,
            variance: 5000,
            status: "approved",
            description: "Foundation concrete",
          },
        ],
      },
      setSelectedItem: setSelectedMock,
    });

    const { container } = renderWithProviders(<ProjectBudgetPage />);
    const editBtns = container.querySelectorAll("table button");
    if (editBtns.length > 0) fireEvent.click(editBtns[0]);

    await waitFor(() => {
      expect(setSelectedMock).toHaveBeenCalled();
    });
  });

  it("calls confirm and deleteItem via table action button", async () => {
    const deleteMock = vi.fn().mockResolvedValue(undefined);
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);

    useBudgetMock.mockReturnValue({
      ...defaultBudgetMock,
      budget: {
        ...defaultBudgetMock.budget,
        items: [
          {
            id: "item-del",
            name: "To Delete",
            category: "other",
            amount: 1000,
            actualAmount: 0,
            status: "planned",
          },
        ],
      },
      deleteItem: deleteMock,
    });

    const { container } = renderWithProviders(<ProjectBudgetPage />);
    const tableBtns = container.querySelectorAll("table button");
    fireEvent.click(tableBtns[tableBtns.length - 1]);

    await waitFor(() => {
      expect(confirmSpy).toHaveBeenCalled();
      expect(deleteMock).toHaveBeenCalledWith("item-del");
    });
  });

  it("does not call deleteItem when confirm returns false", async () => {
    const deleteMock = vi.fn();
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(false);

    useBudgetMock.mockReturnValue({
      ...defaultBudgetMock,
      budget: {
        ...defaultBudgetMock.budget,
        items: [
          {
            id: "item-keep",
            name: "Keep",
            category: "other",
            amount: 1000,
            actualAmount: 0,
            status: "planned",
          },
        ],
      },
      deleteItem: deleteMock,
    });

    const { container } = renderWithProviders(<ProjectBudgetPage />);
    const tableBtns = container.querySelectorAll("table button");
    fireEvent.click(tableBtns[tableBtns.length - 1]);

    await waitFor(() => {
      expect(confirmSpy).toHaveBeenCalled();
    });
    expect(deleteMock).not.toHaveBeenCalled();
  });

  it("renders category breakdown when items have categories", () => {
    useBudgetMock.mockReturnValue({
      ...defaultBudgetMock,
      budget: {
        ...defaultBudgetMock.budget,
        items: [
          {
            id: "item-1",
            name: "Concrete",
            category: "materials",
            amount: 50000,
            actualAmount: 45000,
            status: "approved",
          },
          {
            id: "item-2",
            name: "Steel",
            category: "labor",
            amount: 30000,
            actualAmount: 35000,
            status: "approved",
          },
        ],
      },
    });

    renderWithProviders(<ProjectBudgetPage />);
    expect(screen.getByText("Category Breakdown")).toBeInTheDocument();
  });

  it("renders variance chart when items have amounts", () => {
    useBudgetMock.mockReturnValue({
      ...defaultBudgetMock,
      budget: {
        ...defaultBudgetMock.budget,
        items: [
          {
            id: "item-1",
            name: "Concrete",
            category: "materials",
            amount: 50000,
            actualAmount: 45000,
            status: "approved",
          },
        ],
      },
    });

    renderWithProviders(<ProjectBudgetPage />);
    expect(screen.getByText("Planned vs Actual")).toBeInTheDocument();
  });

  it("calculates safeUtilization from total when utilization is 0", () => {
    useBudgetMock.mockReturnValue({
      ...defaultBudgetMock,
      budget: {
        ...defaultBudgetMock.budget,
        utilization_percentage: 0,
        total_budget: 100000,
        spent_amount: 60000,
      },
    });

    renderWithProviders(<ProjectBudgetPage />);
    expect(screen.getByTestId("budget-utilization")).toHaveTextContent("60%");
  });

  it("shows 0% when both utilization and total are 0", () => {
    useBudgetMock.mockReturnValue({
      ...defaultBudgetMock,
      budget: {
        ...defaultBudgetMock.budget,
        utilization_percentage: 0,
        total_budget: 0,
        spent_amount: 0,
      },
    });

    renderWithProviders(<ProjectBudgetPage />);
    expect(screen.getByTestId("budget-utilization")).toHaveTextContent("0%");
  });

  it("defaults currency to EUR when not provided", () => {
    useBudgetMock.mockReturnValue({
      ...defaultBudgetMock,
      budget: {
        ...defaultBudgetMock.budget,
        total_budget: 0,
        spent_amount: 0,
        currency: undefined,
      },
    });

    renderWithProviders(<ProjectBudgetPage />);
    expect(screen.getByTestId("total-budget")).toHaveTextContent("€0");
  });

  it("shows Unknown when variance_status is empty", () => {
    useBudgetMock.mockReturnValue({
      ...defaultBudgetMock,
      budget: {
        ...defaultBudgetMock.budget,
        variance_status: "",
      },
    });

    renderWithProviders(<ProjectBudgetPage />);
    expect(screen.getByTestId("budget-variance")).toHaveTextContent("Unknown");
  });
});
