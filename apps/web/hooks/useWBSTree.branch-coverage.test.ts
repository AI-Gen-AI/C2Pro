/**
 * Test Suite ID: TS-QA-337-WBSTREE-BRANCH-COV
 * Branch coverage tests for useWBSTree hook
 */
import { renderHook, act } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { createTestWrapper } from "@/src/tests/test-utils";
import { useWBSTree } from "./useWBSTree";

const { createMutateAsyncMock, updateMutateAsyncMock, deleteMutateAsyncMock, moveMutateAsyncMock, refetchMock, getMockData } = vi.hoisted(() => ({
  createMutateAsyncMock: vi.fn(),
  updateMutateAsyncMock: vi.fn(),
  deleteMutateAsyncMock: vi.fn(),
  moveMutateAsyncMock: vi.fn(),
  refetchMock: vi.fn(),
  getMockData: vi.fn(() => ({ items: [] as unknown[] })),
}));

vi.mock("@/lib/api/generated/wbs/wbs", () => ({
  getGetWbsApiV1ProjectsProjectIdWbsGetQueryKey: (projectId: string) => [
    "wbs",
    projectId,
  ],
  useGetWbsApiV1ProjectsProjectIdWbsGet: () => ({
    data: getMockData(),
    isLoading: false,
    isError: false,
    error: null,
    refetch: refetchMock,
  }),
  useCreateWbsItemApiV1ProjectsProjectIdWbsItemsPost: () => ({
    mutateAsync: createMutateAsyncMock,
  }),
  useUpdateWbsItemApiV1ProjectsProjectIdWbsItemsItemIdPatch: () => ({
    mutateAsync: updateMutateAsyncMock,
  }),
  useDeleteWbsItemApiV1ProjectsProjectIdWbsItemsItemIdDelete: () => ({
    mutateAsync: deleteMutateAsyncMock,
  }),
  useMoveWbsItemApiV1ProjectsProjectIdWbsItemsItemIdMovePost: () => ({
    mutateAsync: moveMutateAsyncMock,
  }),
}));

describe("useWBSTree branch coverage", () => {
  beforeEach(() => {
    createMutateAsyncMock.mockReset();
    updateMutateAsyncMock.mockReset();
    deleteMutateAsyncMock.mockReset();
    moveMutateAsyncMock.mockReset();
    refetchMock.mockReset();
    getMockData.mockReturnValue({ items: [] });
  });

  it("transforms flat items into tree with parent_id mapping and budget extraction", () => {
    getMockData.mockReturnValue({
      items: [
        {
          id: "wbs-1",
          code: "1",
          name: "Phase 1",
          level: 0,
          completion: 50,
          budget: { allocated: 100000, spent: 50000 },
          start_date: "2026-01-01",
          end_date: "2026-06-30",
          parent_id: null,
        },
        {
          id: "wbs-2",
          code: "1.1",
          name: "Subtask",
          level: 1,
          completion: 30,
          budget: null,
          start_date: null,
          end_date: null,
          parent_id: "wbs-1",
        },
      ],
    });

    const { result } = renderHook(
      () => useWBSTree({ projectId: "proj-wbs" }),
      { wrapper: createTestWrapper() },
    );

    expect(result.current.items).toHaveLength(1);
    expect(result.current.items[0].id).toBe("wbs-1");
    expect(result.current.items[0].children).toHaveLength(1);
    expect(result.current.items[0].children[0].id).toBe("wbs-2");
    expect(result.current.items[0].budgetAllocated).toBe(100000);
    expect(result.current.items[0].budgetSpent).toBe(50000);
    expect(result.current.items[0].plannedStart).toBe("2026-01-01");
    expect(result.current.items[0].children[0].budgetAllocated).toBeUndefined();
  });

  it("handles orphan items (parent_id missing from map) as root items", () => {
    getMockData.mockReturnValue({
      items: [
        {
          id: "wbs-orphan",
          code: "X",
          name: "Orphan",
          level: 0,
          completion: 0,
          budget: undefined,
          start_date: undefined,
          end_date: undefined,
          parent_id: "nonexistent-parent",
        },
      ],
    });

    const { result } = renderHook(
      () => useWBSTree({ projectId: "proj-wbs" }),
      { wrapper: createTestWrapper() },
    );

    expect(result.current.items).toHaveLength(1);
    expect(result.current.items[0].id).toBe("wbs-orphan");
  });

  it("returns null from createItem when mutateAsync returns falsy", async () => {
    createMutateAsyncMock.mockResolvedValue(null);

    const { result } = renderHook(
      () => useWBSTree({ projectId: "proj-wbs" }),
      { wrapper: createTestWrapper() },
    );

    const created = await result.current.createItem({
      code: "2",
      name: "New Item",
    });
    expect(created).toBeNull();
  });

  it("returns a WBSTreeItem from createItem on success", async () => {
    createMutateAsyncMock.mockResolvedValue({
      id: "wbs-new",
      code: "2",
      name: "New Item",
      level: 0,
      completion: 0,
      start_date: null,
      end_date: null,
    });

    const { result } = renderHook(
      () => useWBSTree({ projectId: "proj-wbs" }),
      { wrapper: createTestWrapper() },
    );

    const created = await result.current.createItem({
      code: "2",
      name: "New Item",
    });
    expect(created).toEqual(
      expect.objectContaining({ id: "wbs-new", name: "New Item" }),
    );
    expect(refetchMock).toHaveBeenCalled();
  });

  it("returns null from updateItem when mutateAsync returns falsy", async () => {
    updateMutateAsyncMock.mockResolvedValue(undefined);

    const { result } = renderHook(
      () => useWBSTree({ projectId: "proj-wbs" }),
      { wrapper: createTestWrapper() },
    );

    const updated = await result.current.updateItem("wbs-1", {
      name: "Updated",
    });
    expect(updated).toBeNull();
  });

  it("returns a WBSTreeItem from updateItem on success", async () => {
    updateMutateAsyncMock.mockResolvedValue({
      id: "wbs-1",
      code: "1",
      name: "Updated",
      level: 0,
      completion: 100,
      start_date: null,
      end_date: null,
    });

    const { result } = renderHook(
      () => useWBSTree({ projectId: "proj-wbs" }),
      { wrapper: createTestWrapper() },
    );

    const updated = await result.current.updateItem("wbs-1", {
      name: "Updated",
    });
    expect(updated).toEqual(
      expect.objectContaining({ id: "wbs-1", name: "Updated" }),
    );
    expect(refetchMock).toHaveBeenCalled();
  });

  it("deleteItem clears selectedItem when deleted item matches", async () => {
    deleteMutateAsyncMock.mockResolvedValue(undefined);

    const { result } = renderHook(
      () => useWBSTree({ projectId: "proj-wbs" }),
      { wrapper: createTestWrapper() },
    );

    act(() => {
      result.current.setSelectedItem({
        id: "wbs-1",
        code: "1",
        name: "To Delete",
        level: 0,
        completion: 0,
        children: [],
      });
    });

    await act(async () => {
      const deleted = await result.current.deleteItem("wbs-1", true);
      expect(deleted).toBe(true);
    });

    expect(result.current.selectedItem).toBeNull();
    expect(deleteMutateAsyncMock).toHaveBeenCalledWith(
      expect.objectContaining({
        params: { cascade: true },
      }),
    );
  });

  it("deleteItem does not clear selectedItem when deleted item differs", async () => {
    deleteMutateAsyncMock.mockResolvedValue(undefined);

    const { result } = renderHook(
      () => useWBSTree({ projectId: "proj-wbs" }),
      { wrapper: createTestWrapper() },
    );

    act(() => {
      result.current.setSelectedItem({
        id: "wbs-other",
        code: "2",
        name: "Other",
        level: 0,
        completion: 0,
        children: [],
      });
    });

    await act(async () => {
      await result.current.deleteItem("wbs-1");
    });

    expect(result.current.selectedItem?.id).toBe("wbs-other");
  });

  it("toggleExpanded adds and removes items from expanded set", () => {
    const { result } = renderHook(
      () => useWBSTree({ projectId: "proj-wbs" }),
      { wrapper: createTestWrapper() },
    );

    act(() => result.current.toggleExpanded("wbs-1"));
    expect(result.current.expandedItems.has("wbs-1")).toBe(true);

    act(() => result.current.toggleExpanded("wbs-1"));
    expect(result.current.expandedItems.has("wbs-1")).toBe(false);
  });

  it("expandAll collects all parent IDs and collapseAll clears them", () => {
    getMockData.mockReturnValue({
      items: [
        {
          id: "wbs-1",
          code: "1",
          name: "Parent",
          level: 0,
          completion: 0,
          budget: undefined,
          start_date: undefined,
          end_date: undefined,
          parent_id: null,
        },
        {
          id: "wbs-2",
          code: "1.1",
          name: "Child",
          level: 1,
          completion: 0,
          budget: undefined,
          start_date: undefined,
          end_date: undefined,
          parent_id: "wbs-1",
        },
      ],
    });

    const { result } = renderHook(
      () => useWBSTree({ projectId: "proj-wbs" }),
      { wrapper: createTestWrapper() },
    );

    act(() => result.current.expandAll());
    expect(result.current.expandedItems.has("wbs-1")).toBe(true);
    expect(result.current.expandedItems.size).toBe(1);

    act(() => result.current.collapseAll());
    expect(result.current.expandedItems.size).toBe(0);
  });

  it("moveItem calls mutateAsync and refetches", async () => {
    moveMutateAsyncMock.mockResolvedValue(undefined);

    const { result } = renderHook(
      () => useWBSTree({ projectId: "proj-wbs" }),
      { wrapper: createTestWrapper() },
    );

    const moved = await result.current.moveItem("wbs-2", "wbs-1");
    expect(moved).toBe(true);
    expect(moveMutateAsyncMock).toHaveBeenCalledWith(
      expect.objectContaining({
        projectId: "proj-wbs",
        itemId: "wbs-2",
        data: { new_parent_id: "wbs-1" },
      }),
    );
    expect(refetchMock).toHaveBeenCalled();
  });
});
