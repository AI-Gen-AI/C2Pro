/**
 * Test Suite ID: TS-QA-337-USE-BUDGET-BRANCH-COV
 * Branch coverage tests for useBudget hook
 */
import { renderHook, act, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { createTestWrapper } from "@/src/tests/test-utils";
import {
  useBudget,
  calculateCategoryBreakdown,
  calculateVarianceData,
} from "./useBudget";

const { apiClientMock } = vi.hoisted(() => ({
  apiClientMock: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}));

vi.mock("@/lib/api/client", () => ({
  apiClient: apiClientMock,
}));

describe("useBudget branch coverage", () => {
  beforeEach(() => {
    apiClientMock.get.mockReset();
    apiClientMock.post.mockReset();
    apiClientMock.patch.mockReset();
    apiClientMock.delete.mockReset();
  });

  it("fetches budget data and returns BudgetSummary", async () => {
    apiClientMock.get.mockResolvedValue({
      data: {
        total_budget: 100000,
        spent_amount: 40000,
        remaining_budget: 60000,
        utilization_percentage: 40,
        variance_status: "On Track",
        currency: "EUR",
        items: [],
      },
    });

    const { result } = renderHook(
      () => useBudget({ projectId: "proj-budget" }),
      { wrapper: createTestWrapper() },
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.budget).toEqual(
      expect.objectContaining({ total_budget: 100000 }),
    );
    expect(result.current.isError).toBe(false);
  });

  it("returns null budget when query returns no data", async () => {
    apiClientMock.get.mockResolvedValue({ data: null });

    const { result } = renderHook(
      () => useBudget({ projectId: "proj-budget" }),
      { wrapper: createTestWrapper() },
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.budget).toBeNull();
  });

  it("createItem returns the created item on success", async () => {
    apiClientMock.get.mockResolvedValue({ data: null });
    apiClientMock.post.mockResolvedValue({
      data: {
        id: "new-item",
        name: "Concrete",
        category: "materials",
        amount: 5000,
        status: "planned",
      },
    });

    const { result } = renderHook(
      () => useBudget({ projectId: "proj-budget" }),
      { wrapper: createTestWrapper() },
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    const item = await result.current.createItem({
      name: "Concrete",
      amount: 5000,
    });
    expect(item).toEqual(expect.objectContaining({ id: "new-item" }));
  });

  it("updateItem returns the updated item on success", async () => {
    apiClientMock.get.mockResolvedValue({ data: null });
    apiClientMock.patch.mockResolvedValue({
      data: {
        id: "item-1",
        name: "Updated Concrete",
        amount: 6000,
      },
    });

    const { result } = renderHook(
      () => useBudget({ projectId: "proj-budget" }),
      { wrapper: createTestWrapper() },
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    const item = await result.current.updateItem("item-1", {
      name: "Updated Concrete",
    });
    expect(item).toEqual(expect.objectContaining({ id: "item-1" }));
  });

  it("deleteItem clears selectedItem when IDs match", async () => {
    apiClientMock.get.mockResolvedValue({ data: null });
    apiClientMock.delete.mockResolvedValue({});

    const { result } = renderHook(
      () => useBudget({ projectId: "proj-budget" }),
      { wrapper: createTestWrapper() },
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    act(() => {
      result.current.setSelectedItem({
        id: "item-del",
        name: "To Delete",
        category: "other",
        amount: 100,
        status: "planned",
      });
    });

    await act(async () => {
      const deleted = await result.current.deleteItem("item-del");
      expect(deleted).toBe(true);
    });

    expect(result.current.selectedItem).toBeNull();
  });

  it("deleteItem does not clear selectedItem when IDs differ", async () => {
    apiClientMock.get.mockResolvedValue({ data: null });
    apiClientMock.delete.mockResolvedValue({});

    const { result } = renderHook(
      () => useBudget({ projectId: "proj-budget" }),
      { wrapper: createTestWrapper() },
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    act(() => {
      result.current.setSelectedItem({
        id: "item-other",
        name: "Other",
        category: "other",
        amount: 100,
        status: "planned",
      });
    });

    await act(async () => {
      await result.current.deleteItem("item-del");
    });

    expect(result.current.selectedItem?.id).toBe("item-other");
  });

  it("returns isError and error on fetch failure", async () => {
    apiClientMock.get.mockRejectedValue(new Error("Network error"));

    const { result } = renderHook(
      () => useBudget({ projectId: "proj-budget" }),
      { wrapper: createTestWrapper() },
    );

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error).toBeInstanceOf(Error);
  });
});

describe("calculateCategoryBreakdown", () => {
  it("groups items by category using actualAmount fallback", () => {
    const items = [
      {
        id: "1",
        name: "Concrete",
        category: "materials",
        amount: 50000,
        actualAmount: 45000,
        status: "approved",
      },
      {
        id: "2",
        name: "Steel",
        category: "materials",
        amount: 30000,
        actualAmount: undefined,
        status: "approved",
      },
      {
        id: "3",
        name: "Labor",
        category: "labor",
        amount: 20000,
        actualAmount: 20000,
        status: "approved",
      },
    ];

    const breakdown = calculateCategoryBreakdown(items);
    expect(breakdown).toHaveLength(2);

    const materials = breakdown.find((b) => b.name === "materials");
    expect(materials?.planned).toBe(80000);
    expect(materials?.actual).toBe(75000);
    expect(materials?.variance).toBe(5000);

    const labor = breakdown.find((b) => b.name === "labor");
    expect(labor?.planned).toBe(20000);
    expect(labor?.actual).toBe(20000);
    expect(labor?.variance).toBe(0);
  });

  it("returns empty array for empty items", () => {
    expect(calculateCategoryBreakdown([])).toEqual([]);
  });
});

describe("calculateVarianceData", () => {
  it("calculates variance using actualAmount fallback", () => {
    const items = [
      {
        id: "1",
        name: "Concrete",
        category: "materials",
        amount: 50000,
        actualAmount: 45000,
        status: "approved",
      },
      {
        id: "2",
        name: "Steel",
        category: "materials",
        amount: 30000,
        actualAmount: undefined,
        status: "approved",
      },
    ];

    const variance = calculateVarianceData(items);
    expect(variance).toHaveLength(2);
    expect(variance[0].variance).toBe(5000);
    expect(variance[1].variance).toBe(0);
  });

  it("uses explicit variance when provided", () => {
    const items = [
      {
        id: "1",
        name: "Concrete",
        category: "materials",
        amount: 50000,
        actualAmount: 45000,
        variance: 8000,
        status: "approved",
      },
    ];

    const variance = calculateVarianceData(items);
    expect(variance[0].variance).toBe(8000);
  });

  it("returns empty array for empty items", () => {
    expect(calculateVarianceData([])).toEqual([]);
  });
});
