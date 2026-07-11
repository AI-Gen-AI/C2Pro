/**
 * Test Suite ID: TS-FRT-MUT-ERR-001
 */
import { renderHook } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { createTestWrapper } from "@/src/tests/test-utils";
import { useWBSTree } from "./useWBSTree";

const createMutateAsyncMock = vi.fn();
const updateMutateAsyncMock = vi.fn();
const deleteMutateAsyncMock = vi.fn();
const moveMutateAsyncMock = vi.fn();
const refetchMock = vi.fn();

vi.mock("@/lib/api/generated/wbs/wbs", () => ({
  getGetWbsApiV1ProjectsProjectIdWbsGetQueryKey: (projectId: string) => [
    "wbs",
    projectId,
  ],
  useGetWbsApiV1ProjectsProjectIdWbsGet: () => ({
    data: { items: [] },
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

describe("useWBSTree mutation errors", () => {
  beforeEach(() => {
    createMutateAsyncMock.mockReset();
    updateMutateAsyncMock.mockReset();
    deleteMutateAsyncMock.mockReset();
    moveMutateAsyncMock.mockReset();
    refetchMock.mockReset();
  });

  it("propagates create failures instead of returning null", async () => {
    createMutateAsyncMock.mockRejectedValueOnce(new Error("WBS create failed"));

    const { result } = renderHook(
      () => useWBSTree({ projectId: "proj-wbs" }),
      { wrapper: createTestWrapper() },
    );

    await expect(
      result.current.createItem({ code: "1", name: "Mobilization" }),
    ).rejects.toThrow("WBS create failed");
  });

  it("propagates move failures instead of returning false", async () => {
    moveMutateAsyncMock.mockRejectedValueOnce(new Error("WBS move failed"));

    const { result } = renderHook(
      () => useWBSTree({ projectId: "proj-wbs" }),
      { wrapper: createTestWrapper() },
    );

    await expect(result.current.moveItem("wbs-1", null)).rejects.toThrow(
      "WBS move failed",
    );
  });
});
