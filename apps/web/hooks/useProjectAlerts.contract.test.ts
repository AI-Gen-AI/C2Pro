/**
 * PC-7b (#672, board #1049): useProjectAlerts must call the real, served alerts
 * route and never fabricate a source clause id. See the hook's own header comment
 * for the route-wiring verification against apps/api/src/alerts/adapters/http/router.py.
 */
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
});

async function runMapping(items: unknown[], expected: unknown[]) {
  getMock.mockResolvedValueOnce({ data: { items, total: items.length } });

  const { result } = renderHook(() => useProjectAlerts("proj-mapping"));

  await waitFor(() => expect(result.current.loading).toBe(false));

  expect(result.current.alerts).toEqual(expected);
}
