/**
 * Test Suite ID: TS-FRT-WBS-CONTRACT-001
 * useWBSTree consumes the authoritative GET /projects/{id}/wbs contract (IR-4):
 * root items with nested `children`, procurement fields, and no write operations
 * (the in-memory write routes it used to call are no longer served).
 */
import { renderHook, act } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createTestWrapper } from "@/src/tests/test-utils";
import { useWBSTree } from "./useWBSTree";

const { getMockData, refetchMock } = vi.hoisted(() => ({
  getMockData: vi.fn(() => undefined as unknown),
  refetchMock: vi.fn(),
}));

vi.mock("@/lib/api/generated/projects/projects", () => ({
  getGetProjectWbsApiV1ProjectsProjectIdWbsGetQueryKey: (projectId: string) => [
    "wbs",
    projectId,
  ],
  useGetProjectWbsApiV1ProjectsProjectIdWbsGet: () => ({
    data: getMockData(),
    isLoading: false,
    isError: false,
    error: null,
    refetch: refetchMock,
  }),
}));

function node(overrides: Record<string, unknown>) {
  return {
    id: "n",
    project_id: "proj-wbs",
    code: "1",
    name: "Node",
    level: 1,
    description: null,
    parent_code: null,
    item_type: null,
    budget_allocated: null,
    budget_spent: 0,
    planned_start: null,
    planned_end: null,
    actual_start: null,
    actual_end: null,
    source_clause_id: null,
    version: 1,
    metadata: {},
    children: [],
    ...overrides,
  };
}

const runtimePayload = {
  project_id: "proj-wbs",
  items: [
    node({
      id: "root",
      code: "1",
      name: "Harbour Extension",
      item_type: "deliverable",
      budget_allocated: 1500000,
      children: [
        node({
          id: "child",
          code: "1.1",
          name: "Quay wall",
          level: 2,
          parent_code: "1",
          item_type: "work_package",
          budget_allocated: 900000.5,
          budget_spent: 12.25,
          planned_start: "2026-10-01T00:00:00+00:00",
          planned_end: "2027-06-30T00:00:00+00:00",
          children: [
            node({ id: "grandchild", code: "1.1.1", name: "Piling", level: 3, parent_code: "1.1" }),
          ],
        }),
      ],
    }),
    node({ id: "root-2", code: "2", name: "Dredging" }),
  ],
  coverage: {
    total_items: 4,
    items_with_budget: 2,
    items_with_dates: 1,
    items_with_alerts: 0,
    completion_average: 0,
  },
  alerts: [],
  total_items: 4,
};

describe("useWBSTree (authoritative WBS contract)", () => {
  beforeEach(() => {
    getMockData.mockReset();
    refetchMock.mockReset();
  });

  it("keeps the served hierarchy and maps procurement fields", () => {
    getMockData.mockReturnValue(runtimePayload);
    const { result } = renderHook(() => useWBSTree({ projectId: "proj-wbs" }), {
      wrapper: createTestWrapper(),
    });

    const [root, secondRoot] = result.current.items;
    expect(result.current.items.map((item) => item.id)).toEqual(["root", "root-2"]);
    expect(root.children.map((item) => item.id)).toEqual(["child"]);
    expect(root.children[0].children.map((item) => item.code)).toEqual(["1.1.1"]);
    expect(root.children[0]).toMatchObject({
      code: "1.1",
      name: "Quay wall",
      level: 2,
      itemType: "work_package",
      budgetAllocated: 900000.5,
      budgetSpent: 12.25,
      plannedStart: "2026-10-01T00:00:00+00:00",
      plannedEnd: "2027-06-30T00:00:00+00:00",
    });
    expect(secondRoot.children).toEqual([]);
    expect(result.current.totalItems).toBe(4);
  });

  it("does not invent progress the contract does not carry", () => {
    getMockData.mockReturnValue(runtimePayload);
    const { result } = renderHook(() => useWBSTree({ projectId: "proj-wbs" }), {
      wrapper: createTestWrapper(),
    });

    expect(result.current.items[0]).not.toHaveProperty("completion");
  });

  it("exposes no write operations", () => {
    getMockData.mockReturnValue(runtimePayload);
    const { result } = renderHook(() => useWBSTree({ projectId: "proj-wbs" }), {
      wrapper: createTestWrapper(),
    });

    for (const key of ["createItem", "updateItem", "deleteItem", "moveItem"]) {
      expect(result.current).not.toHaveProperty(key);
    }
  });

  it("expands every node that has children, at any depth, and collapses them", () => {
    getMockData.mockReturnValue(runtimePayload);
    const { result } = renderHook(() => useWBSTree({ projectId: "proj-wbs" }), {
      wrapper: createTestWrapper(),
    });

    act(() => result.current.expandAll());
    expect([...result.current.expandedItems].sort()).toEqual(["child", "root"]);

    act(() => result.current.toggleExpanded("child"));
    expect(result.current.expandedItems.has("child")).toBe(false);

    act(() => result.current.collapseAll());
    expect(result.current.expandedItems.size).toBe(0);
  });

  it("returns an empty tree and unknown total while nothing is loaded", () => {
    getMockData.mockReturnValue(undefined);
    const { result } = renderHook(() => useWBSTree({ projectId: "proj-wbs" }), {
      wrapper: createTestWrapper(),
    });

    expect(result.current.items).toEqual([]);
    expect(result.current.totalItems).toBeNull();
  });
});
