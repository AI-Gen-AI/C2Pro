import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useProjectOverview } from "@/hooks/useProjectOverview";

const { getMock } = vi.hoisted(() => ({
  getMock: vi.fn(),
}));

vi.mock("@/lib/api/client", () => ({
  apiClient: {
    get: getMock,
  },
}));

describe("useProjectOverview", () => {
  beforeEach(() => {
    getMock.mockReset();
  });

  it("loads dashboard and alert data into overview stats", async () => {
    getMock
      .mockResolvedValueOnce({
        data: {
          coherence_score: 88,
          alert_count: 4,
          document_count: 7,
          sub_scores: { BUDGET: 30 },
        },
      })
      .mockResolvedValueOnce({
        data: {
          items: [
            { id: "a-1", severity: "critical", status: "open", message: "Delay issue — details" },
            { id: "a-2", severity: "high", status: "resolved", message: "Resolved issue" },
            { id: "a-3", severity: "medium", status: "open", message: "Budget warning — more" },
          ],
          total: 3,
        },
      });

    const { result } = renderHook(() => useProjectOverview("proj-1"));

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(getMock).toHaveBeenNthCalledWith(1, "/coherence/dashboard/proj-1");
    expect(getMock).toHaveBeenNthCalledWith(2, "/projects/proj-1/alerts");
    expect(result.current.stats).toEqual({
      coherenceScore: 88,
      openAlerts: 2,
      documentCount: 7,
      budgetUsed: 70,
      recentAlerts: [
        { severity: "critical", title: "Delay issue" },
        { severity: "medium", title: "Budget warning" },
      ],
    });
  });

  it("caps recent alerts to the first three open entries", async () => {
    getMock
      .mockResolvedValueOnce({
        data: {
          coherence_score: 75,
          alert_count: 5,
          document_count: 2,
          sub_scores: { BUDGET: 60 },
        },
      })
      .mockResolvedValueOnce({
        data: {
          items: [
            { id: "a-1", severity: "critical", status: "open", message: "One" },
            { id: "a-2", severity: "high", status: "open", message: "Two" },
            { id: "a-3", severity: "medium", status: "open", message: "Three" },
            { id: "a-4", severity: "low", status: "open", message: "Four" },
          ],
          total: 4,
        },
      });

    const { result } = renderHook(() => useProjectOverview("proj-2"));

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.stats?.recentAlerts).toEqual([
      { severity: "critical", title: "One" },
      { severity: "high", title: "Two" },
      { severity: "medium", title: "Three" },
    ]);
  });

  it("surfaces request failures as stable errors", async () => {
    getMock.mockRejectedValueOnce(new Error("dashboard down"));

    const { result } = renderHook(() => useProjectOverview("proj-3"));

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.stats).toBeNull();
    expect(result.current.error?.message).toBe("dashboard down");
  });

  it("uses a zero budget fallback when the dashboard omits BUDGET scoring", async () => {
    getMock
      .mockResolvedValueOnce({
        data: {
          coherence_score: 62,
          alert_count: 0,
          document_count: 3,
          sub_scores: { TIME: 80 },
        },
      })
      .mockResolvedValueOnce({
        data: {
          items: [],
          total: 0,
        },
      });

    const { result } = renderHook(() => useProjectOverview("proj-5"));

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.stats).toMatchObject({
      coherenceScore: 62,
      openAlerts: 0,
      documentCount: 3,
      budgetUsed: 100,
      recentAlerts: [],
    });
  });

  it("normalizes non-Error failures to a stable overview error", async () => {
    getMock.mockRejectedValueOnce("timeout");

    const { result } = renderHook(() => useProjectOverview("proj-6"));

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.error?.message).toBe("Failed to fetch project overview");
    expect(result.current.stats).toBeNull();
  });

  it("ignores late responses after unmount", async () => {
    let resolveDashboard: ((value: unknown) => void) | undefined;
    let resolveAlerts: ((value: unknown) => void) | undefined;
    getMock
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveDashboard = resolve;
          }),
      )
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveAlerts = resolve;
          }),
      );

    const { result, unmount } = renderHook(() => useProjectOverview("proj-4"));
    unmount();

    resolveDashboard?.({
      data: { coherence_score: 40, alert_count: 1, document_count: 1, sub_scores: { BUDGET: 90 } },
    });
    resolveAlerts?.({
      data: { items: [{ id: "a-1", severity: "low", status: "open", message: "Late" }], total: 1 },
    });

    await waitFor(() => expect(result.current.loading).toBe(true));
    expect(result.current.stats).toBeNull();
  });
});
