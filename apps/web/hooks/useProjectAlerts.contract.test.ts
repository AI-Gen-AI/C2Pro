import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useProjectAlerts } from "@/hooks/useProjectAlerts";

const { getMock } = vi.hoisted(() => ({
  getMock: vi.fn(),
}));

vi.mock("@/lib/api/client", () => ({
  apiClient: {
    get: getMock,
  },
}));

describe("useProjectAlerts project mapping", () => {
  beforeEach(() => {
    getMock.mockReset();
  });

  it("returns an empty state when the project id is null", async () => {
    const { result } = renderHook(() => useProjectAlerts(null));

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(getMock).not.toHaveBeenCalled();
    expect(result.current.alerts).toEqual([]);
  });

  it("maps unknown severities and statuses to safe defaults", async () => {
    getMock.mockResolvedValueOnce({
      data: {
        items: [
          {
            id: "a-9",
            category: "UNKNOWN",
            severity: "urgent",
            status: "mystery",
            message: "Unexpected payload",
          },
        ],
        total: 1,
      },
    });

    const { result } = renderHook(() => useProjectAlerts("proj-5"));

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.alerts).toEqual([
      {
        id: "a-9",
        title: "Unexpected payload",
        severity: "medium",
        status: "pending",
        clauseId: "clause-a-9",
        assignee: "project.manager",
      },
    ]);
  });

  it("maps known categories and statuses to review ownership semantics", async () => {
    getMock.mockResolvedValueOnce({
      data: {
        items: [
          {
            id: "a-1",
            category: "LEGAL",
            severity: "high",
            status: "open",
            message: "Legal issue",
          },
          {
            id: "a-2",
            category: "QUALITY",
            severity: "low",
            status: "rejected",
            message: "Quality issue",
          },
        ],
        total: 2,
      },
    });

    const { result } = renderHook(() => useProjectAlerts("proj-legal"));

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.alerts).toEqual([
      {
        id: "a-1",
        title: "Legal issue",
        severity: "high",
        status: "pending",
        clauseId: "clause-a-1",
        assignee: "legal.reviewer",
      },
      {
        id: "a-2",
        title: "Quality issue",
        severity: "low",
        status: "rejected",
        clauseId: "clause-a-2",
        assignee: "qa.manager",
      },
    ]);
  });

  it("surfaces backend request failures", async () => {
    getMock.mockRejectedValueOnce(new Error("alerts down"));

    const { result } = renderHook(() => useProjectAlerts("proj-6"));

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.error?.message).toBe("alerts down");
    expect(result.current.alerts).toEqual([]);
  });

  it("clears existing alerts when the project id becomes null", async () => {
    getMock.mockResolvedValueOnce({
      data: {
        items: [
          {
            id: "a-3",
            category: "TIME",
            severity: "critical",
            status: "open",
            message: "Schedule issue",
          },
        ],
        total: 1,
      },
    });

    const initialProps: { projectId: string | null } = {
      projectId: "proj-clear",
    };
    const { result, rerender } = renderHook(
      ({ projectId }: { projectId: string | null }) =>
        useProjectAlerts(projectId),
      { initialProps },
    );

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.alerts).toHaveLength(1);

    rerender({ projectId: null });

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.alerts).toEqual([]);
  });

  it("refetch reloads alert state for the project", async () => {
    getMock
      .mockResolvedValueOnce({
        data: {
          items: [
            {
              id: "a-1",
              category: "LEGAL",
              severity: "high",
              status: "open",
              message: "First alert",
            },
          ],
          total: 1,
        },
      })
      .mockResolvedValueOnce({
        data: {
          items: [
            {
              id: "a-2",
              category: "TIME",
              severity: "critical",
              status: "resolved",
              message: "Second alert",
            },
          ],
          total: 1,
        },
      });

    const { result } = renderHook(() => useProjectAlerts("proj-7"));

    await waitFor(() => expect(result.current.loading).toBe(false));
    await result.current.refetch();

    await waitFor(() =>
      expect(result.current.alerts).toEqual([
        {
          id: "a-2",
          title: "Second alert",
          severity: "critical",
          status: "approved",
          clauseId: "clause-a-2",
          assignee: "scheduler",
        },
      ]),
    );
    expect(getMock).toHaveBeenCalledTimes(2);
  });
});
