import { renderHook } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { createTestWrapper } from "@/src/tests/test-utils";
import { useProjectCoherenceActions } from "@/hooks/useProjectCoherenceActions";

const evaluateMutateAsyncMock = vi.fn();
const analyzeMutateAsyncMock = vi.fn();
const invalidateQueriesMock = vi.fn();
const showToastMock = vi.fn();

vi.mock("@/lib/api/generated/coherence-engine/coherence-engine", () => ({
  useEvaluateProjectCoherenceV0CoherenceEvaluatePost: () => ({
    mutateAsync: evaluateMutateAsyncMock,
    isPending: false,
  }),
}));

vi.mock("@/lib/api/generated/analysis/analysis", () => ({
  useAnalyzeDocumentApiV1AnalyzePost: () => ({
    mutateAsync: analyzeMutateAsyncMock,
    isPending: false,
  }),
}));

vi.mock("@tanstack/react-query", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@tanstack/react-query")>();
  return {
    ...actual,
    useQueryClient: () => ({
      invalidateQueries: invalidateQueriesMock,
    }),
  };
});

vi.mock("@/lib/ui/toast", () => ({
  showToast: (...args: unknown[]) => showToastMock(...args),
}));

describe("useProjectCoherenceActions", () => {
  beforeEach(() => {
    evaluateMutateAsyncMock.mockReset();
    analyzeMutateAsyncMock.mockReset();
    invalidateQueriesMock.mockReset();
    showToastMock.mockReset();
  });

  it("evaluates coherence with the backend request contract and invalidates dashboard data", async () => {
    evaluateMutateAsyncMock.mockResolvedValueOnce({
      alerts: [{ id: "a1" }, { id: "a2" }],
    });

    const { result } = renderHook(
      () => useProjectCoherenceActions("proj-real-1"),
      { wrapper: createTestWrapper() },
    );

    await result.current.evaluateCoherence();

    expect(evaluateMutateAsyncMock).toHaveBeenCalledWith({
      data: { project_id: "proj-real-1" },
    });
    expect(invalidateQueriesMock).toHaveBeenCalledWith({
      queryKey: ["/coherence/dashboard/proj-real-1"],
    });
    expect(invalidateQueriesMock).toHaveBeenCalledWith({
      queryKey: ["/api/v1/projects/proj-real-1/alerts"],
    });
    expect(showToastMock).toHaveBeenCalledWith("Evaluated 0 clauses, 2 findings.");
  });

  it("re-runs analysis with the backend request contract and refreshes project state", async () => {
    analyzeMutateAsyncMock.mockResolvedValueOnce({
      messages: ["preview completed"],
    });

    const { result } = renderHook(
      () => useProjectCoherenceActions("proj-real-2"),
      { wrapper: createTestWrapper() },
    );

    await result.current.rerunAnalysis();

    expect(analyzeMutateAsyncMock).toHaveBeenCalledWith({
      data: { project_id: "proj-real-2" },
    });
    expect(invalidateQueriesMock).toHaveBeenCalledWith({
      queryKey: ["/coherence/dashboard/proj-real-2"],
    });
    expect(invalidateQueriesMock).toHaveBeenCalledWith({
      queryKey: ["/api/v1/projects/proj-real-2/alerts"],
    });
    expect(showToastMock).toHaveBeenCalledWith("Analysis preview completed.");
  });
});
