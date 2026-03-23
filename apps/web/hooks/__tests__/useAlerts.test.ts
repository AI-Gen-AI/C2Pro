import { waitFor, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useAlerts } from "@/hooks/useAlerts";
import { useProjectAlerts } from "@/hooks/useProjectAlerts";

const { getMock } = vi.hoisted(() => ({
  getMock: vi.fn(),
}));

vi.mock("@/lib/api/client", () => ({
  apiClient: {
    get: getMock,
  },
}));

describe("alerts hooks contract alignment", () => {
  beforeEach(() => {
    getMock.mockReset();
  });

  it("useProjectAlerts unwraps backend list response items", async () => {
    getMock.mockResolvedValueOnce({
      data: {
        items: [
          {
            id: "a-1",
            category: "LEGAL",
            severity: "high",
            status: "open",
            message: "Missing permit",
          },
        ],
        total: 1,
      },
    });

    const { result } = renderHook(() => useProjectAlerts("proj-1"));

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(getMock).toHaveBeenCalledWith("/projects/proj-1/alerts");
    expect(result.current.alerts).toEqual([
      {
        id: "a-1",
        title: "Missing permit",
        severity: "high",
        status: "pending",
        clauseId: "clause-a-1",
        assignee: "legal.reviewer",
      },
    ]);
  });

  it("useAlerts consumes canonical alert list wrapper", async () => {
    getMock
      .mockResolvedValueOnce({
        data: {
          items: [
            {
              id: "a-1",
              project_id: "proj-1",
              category: "LEGAL",
              severity: "high",
              status: "open",
              message: "Missing permit",
            },
          ],
          total: 1,
        },
      })
      .mockResolvedValueOnce({
        data: {
          items: [{ id: "proj-1", name: "Project One" }],
        },
      });

    const { result } = renderHook(() => useAlerts());

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(getMock).toHaveBeenNthCalledWith(1, "/alerts");
    expect(result.current.alerts).toEqual([
      {
        id: "a-1",
        severity: "High",
        type: "Legal",
        title: "Missing permit",
        description: "Missing permit",
        project: "Project One",
        status: "Open",
      },
    ]);
  });
});
