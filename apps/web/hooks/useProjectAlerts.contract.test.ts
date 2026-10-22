/**
 * PC-7b (#672, board #1049): useProjectAlerts must call the real, served alerts
 * route and never fabricate a source clause id. See the hook's own header comment
 * for the route-wiring verification against apps/api/src/alerts/adapters/http/router.py.
 *
 * Codex P2 (PR #1059): also covers the fetch-race invariants -- never a fake zero
 * before the first request resolves, never project A's rows under project B, a
 * late A response can never overwrite B (success or failure direction), and a
 * failure always surfaces as `error`, never a silent empty result.
 */
import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useProjectAlerts } from "@/hooks/useProjectAlerts";
import type { ReviewAlert } from "@/components/features/alerts/AlertReviewCenter";

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

  it("calls the real, served GET /alerts/projects/{project_id} route", async () => {
    getMock.mockResolvedValueOnce({ data: { items: [], total: 0 } });

    renderHook(() => useProjectAlerts("proj-5"));

    await waitFor(() => expect(getMock).toHaveBeenCalledWith("/alerts/projects/proj-5"));
  });

  it("maps unknown severities and statuses to safe defaults, without a clause id", () => {
    return runMapping(
      [
        {
          id: "a-9",
          category: "UNKNOWN",
          severity: "urgent",
          status: "mystery",
          message: "Unexpected payload",
        },
      ],
      [
        {
          id: "a-9",
          title: "Unexpected payload",
          severity: "medium",
          status: "pending",
          assignee: "project.manager",
        },
      ],
    );
  });

  it("maps known categories and statuses to review ownership semantics", () => {
    return runMapping(
      [
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
      [
        {
          id: "a-1",
          title: "Legal issue",
          severity: "high",
          status: "pending",
          assignee: "legal.reviewer",
        },
        {
          id: "a-2",
          title: "Quality issue",
          severity: "low",
          status: "rejected",
          assignee: "qa.manager",
        },
      ],
    );
  });

  it("never fabricates a clause id when the backend resolved none", () => {
    return runMapping(
      [
        {
          id: "a-10",
          category: "SCOPE",
          severity: "medium",
          status: "open",
          message: "No evidence resolved yet",
          source_clause_id: null,
          detection_evidence: null,
        },
      ],
      [
        {
          id: "a-10",
          title: "No evidence resolved yet",
          severity: "medium",
          status: "pending",
          assignee: "project.manager",
        },
      ],
    );
  });

  it("surfaces the real persisted source_clause_id and links it to its document", () => {
    return runMapping(
      [
        {
          id: "a-11",
          category: "LEGAL",
          severity: "high",
          status: "open",
          message: "Indemnity clause conflicts with schedule",
          source_clause_id: "clause-§5.2",
          detection_evidence: { source_document_id: "doc-42" },
        },
      ],
      [
        {
          id: "a-11",
          title: "Indemnity clause conflicts with schedule",
          severity: "high",
          status: "pending",
          assignee: "legal.reviewer",
          clauseId: "clause-§5.2",
          addressableClauseId: "clause-§5.2",
          sourceDocumentId: "doc-42",
        },
      ],
    );
  });

  it("falls back to the detector's own evidence clause when nothing is persisted yet", () => {
    return runMapping(
      [
        {
          id: "a-12",
          category: "BUDGET",
          severity: "critical",
          status: "open",
          message: "Line item exceeds approved scope",
          source_clause_id: null,
          detection_evidence: { source_clause_id: "clause-§3.1", source_document_id: "doc-7" },
        },
      ],
      [
        {
          id: "a-12",
          title: "Line item exceeds approved scope",
          severity: "critical",
          status: "pending",
          assignee: "finance.analyst",
          // Unresolved/unpersisted: shown for context, but never a clickable
          // evidence link -- only a persisted source clause is addressable.
          clauseId: "clause-§3.1",
        },
      ],
    );
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
          assignee: "scheduler",
        },
      ]),
    );
    expect(getMock).toHaveBeenCalledTimes(2);
  });

  it("never reports a fake zero/loaded state before the first request resolves", async () => {
    let resolveFetch: ((value: unknown) => void) | undefined;
    getMock.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveFetch = resolve;
        }),
    );

    const history: Array<{ loading: boolean; alertCount: number; error: boolean }> = [];
    const { result } = renderHook(() => {
      const state = useProjectAlerts("proj-slow");
      history.push({
        loading: state.loading,
        alertCount: state.alerts.length,
        error: state.error !== null,
      });
      return state;
    });

    // Every render recorded so far happened before the request resolved: none of
    // them may claim "done loading, 0 alerts, no error" -- that would be a fake
    // empty/zero state the backend never actually reported.
    expect(history.every((snapshot) => snapshot.loading)).toBe(true);
    expect(result.current.loading).toBe(true);
    expect(result.current.alerts).toEqual([]);

    await act(async () => {
      resolveFetch?.({ data: { items: [], total: 0 } });
    });

    await waitFor(() => expect(result.current.loading).toBe(false));
    // Only the final, resolved render may legitimately report an empty list.
    expect(result.current.alerts).toEqual([]);
  });

  it(
    "never shows project A's alerts under project B, and a late A response cannot overwrite B",
    async () => {
      let resolveA: ((value: unknown) => void) | undefined;
      let resolveB: ((value: unknown) => void) | undefined;
      getMock.mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveA = resolve;
          }),
      );
      getMock.mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveB = resolve;
          }),
      );

      const { result, rerender } = renderHook(
        ({ projectId }: { projectId: string }) => useProjectAlerts(projectId),
        { initialProps: { projectId: "proj-a" } },
      );

      // Switch to project B before A's request has resolved.
      rerender({ projectId: "proj-b" });
      expect(result.current.loading).toBe(true);
      expect(result.current.alerts).toEqual([]);

      // A resolves LATE, after B's request has already started.
      await act(async () => {
        resolveA?.({
          data: {
            items: [
              { id: "a-alert", category: "LEGAL", severity: "high", status: "open", message: "From A" },
            ],
            total: 1,
          },
        });
      });
      // A's late response must never be visible once the page has moved on to B.
      expect(result.current.alerts).toEqual([]);
      expect(result.current.loading).toBe(true); // B is still in flight

      await act(async () => {
        resolveB?.({
          data: {
            items: [
              { id: "b-alert", category: "TIME", severity: "low", status: "open", message: "From B" },
            ],
            total: 1,
          },
        });
      });
      await waitFor(() => expect(result.current.loading).toBe(false));
      expect(result.current.alerts.map((a: ReviewAlert) => a.id)).toEqual(["b-alert"]);
    },
  );

  it("does not let a stale failed request overwrite a newer successful one", async () => {
    let rejectA: ((error: Error) => void) | undefined;
    getMock.mockImplementationOnce(
      () =>
        new Promise((_resolve, reject) => {
          rejectA = reject;
        }),
    );
    getMock.mockResolvedValueOnce({
      data: {
        items: [{ id: "b-1", category: "TIME", severity: "low", status: "open", message: "ok" }],
        total: 1,
      },
    });

    const { result, rerender } = renderHook(
      ({ projectId }: { projectId: string }) => useProjectAlerts(projectId),
      { initialProps: { projectId: "proj-a" } },
    );
    rerender({ projectId: "proj-b" });

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.alerts.map((a: ReviewAlert) => a.id)).toEqual(["b-1"]);
    expect(result.current.error).toBeNull();

    // A's request fails LATE, after B already succeeded -- must not surface as
    // an error for the page that has already moved on to B's real result.
    await act(async () => {
      rejectA?.(new Error("stale A failure"));
    });
    expect(result.current.error).toBeNull();
    expect(result.current.alerts.map((a: ReviewAlert) => a.id)).toEqual(["b-1"]);
  });

});

async function runMapping(items: unknown[], expected: unknown[]) {
  getMock.mockResolvedValueOnce({ data: { items, total: items.length } });

  const { result } = renderHook(() => useProjectAlerts("proj-mapping"));

  await waitFor(() => expect(result.current.loading).toBe(false));

  expect(result.current.alerts).toEqual(expected);
}
