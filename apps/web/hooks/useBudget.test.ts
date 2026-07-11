/**
 * Test Suite ID: TS-FRT-MUT-ERR-001
 */
import { describe, expect, it, vi, beforeEach } from "vitest";
import { renderHook } from "@testing-library/react";
import { createTestWrapper } from "@/src/tests/test-utils";
import { useBudget } from "./useBudget";

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

describe("useBudget mutation errors", () => {
  beforeEach(() => {
    apiClientMock.get.mockReset();
    apiClientMock.post.mockReset();
    apiClientMock.patch.mockReset();
    apiClientMock.delete.mockReset();
  });

  it("propagates create item failures instead of returning null", async () => {
    apiClientMock.post.mockRejectedValueOnce(new Error("Budget create failed"));

    const { result } = renderHook(
      () => useBudget({ projectId: "proj-budget", enabled: false }),
      { wrapper: createTestWrapper() },
    );

    await expect(result.current.createItem({ name: "Concrete" })).rejects.toThrow(
      "Budget create failed",
    );
  });

  it("propagates delete item failures instead of returning false", async () => {
    apiClientMock.delete.mockRejectedValueOnce(new Error("Budget delete failed"));

    const { result } = renderHook(
      () => useBudget({ projectId: "proj-budget", enabled: false }),
      { wrapper: createTestWrapper() },
    );

    await expect(result.current.deleteItem("budget-1")).rejects.toThrow(
      "Budget delete failed",
    );
  });
});
