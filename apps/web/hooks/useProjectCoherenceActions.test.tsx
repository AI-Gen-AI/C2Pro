import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { createTestWrapper } from "@/src/tests/test-utils";
import { useProjectCoherenceActions } from "@/hooks/useProjectCoherenceActions";

const evaluateMutateAsyncMock = vi.fn();
const analyzeMutateAsyncMock = vi.fn();
const invalidateQueriesMock = vi.fn();
const showToastMock = vi.fn();

vi.mock("@/lib/api/generated/coherence-engine/coherence-engine", () => ({
  useEvaluateProjectCoherenceApiV1CoherenceEvaluatePost: () => ({
    mutateAsync: evaluateMutateAsyncMock,
    isPending: false,
  }),
}));

vi.mock("@/lib/api/generated/analysis/analysis", () => ({
  useAnalyzeDocumentApiV1AnalysisAnalyzePost: () => ({
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
      queryKey: ["/api/coherence/dashboard/proj-real-1"],
    });
    expect(invalidateQueriesMock).toHaveBeenCalledWith({
      queryKey: ["/api/v1/alerts/projects/proj-real-1"],
    });
    expect(showToastMock).toHaveBeenCalledWith("Evaluated 0 clauses, 2 findings.");
  });

  it("reports a contract awaiting approval as such, never as an evaluation of zero clauses", async () => {
    evaluateMutateAsyncMock.mockResolvedValueOnce({
      overall_score: null,
      alerts: [],
      score_reason: "contract_pending_approval",
    });

    const { result } = renderHook(
      () => useProjectCoherenceActions("proj-pending"),
      { wrapper: createTestWrapper() },
    );
    expect(result.current.contractPendingApproval).toBe(false);

    await act(async () => {
      await result.current.evaluateCoherence();
    });

    expect(result.current.contractPendingApproval).toBe(true);
    expect(showToastMock).toHaveBeenCalledTimes(1);
    expect(showToastMock.mock.calls[0][0]).toMatch(/contract is awaiting approval/i);
    expect(showToastMock.mock.calls[0][0]).not.toMatch(/Evaluated 0 clauses/);
  });

  it("clears the pending state once an evaluation answers normally", async () => {
    evaluateMutateAsyncMock
      .mockResolvedValueOnce({ alerts: [], score_reason: "contract_pending_approval" })
      .mockResolvedValueOnce({ alerts: [{ id: "a1" }] });

    const { result } = renderHook(
      () => useProjectCoherenceActions("proj-pending"),
      { wrapper: createTestWrapper() },
    );
    await act(async () => {
      await result.current.evaluateCoherence();
    });
    await act(async () => {
      await result.current.evaluateCoherence();
    });

    expect(result.current.contractPendingApproval).toBe(false);
    expect(showToastMock).toHaveBeenLastCalledWith("Evaluated 0 clauses, 1 findings.");
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
      queryKey: ["/api/coherence/dashboard/proj-real-2"],
    });
    expect(invalidateQueriesMock).toHaveBeenCalledWith({
      queryKey: ["/api/v1/alerts/projects/proj-real-2"],
    });
    expect(showToastMock).toHaveBeenCalledWith("Analysis preview completed.");
  });
});
