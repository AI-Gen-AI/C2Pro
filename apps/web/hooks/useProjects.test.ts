/**
 * TS-TASK-013-PROJECT-CRUD-001: useProjects hook and dashboard listProjects service coverage.
 */
import { waitFor, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useProjects } from "@/hooks/useProjects";
import { createTestWrapper } from "@/src/tests/test-utils";

const { listProjectsMock } = vi.hoisted(() => ({
  listProjectsMock: vi.fn(),
}));

vi.mock("@/lib/api/services/dashboard", () => ({
  listProjects: listProjectsMock,
}));

describe("useProjects contract alignment", () => {
  beforeEach(() => {
    listProjectsMock.mockReset();
  });

  it("fetches projects from the dashboard service when enabled", async () => {
    listProjectsMock.mockResolvedValueOnce([
      { id: "proj-1", name: "Project One" },
      { id: "proj-2", name: "Project Two" },
    ]);

    const { result } = renderHook(() => useProjects(true), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(listProjectsMock).toHaveBeenCalledTimes(1);
    expect(result.current.data).toEqual([
      { id: "proj-1", name: "Project One" },
      { id: "proj-2", name: "Project Two" },
    ]);
  });

  it("does not fetch when disabled", async () => {
    const { result } = renderHook(() => useProjects(false), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => expect(result.current.fetchStatus).toBe("idle"));

    expect(listProjectsMock).not.toHaveBeenCalled();
    expect(result.current.data).toBeUndefined();
  });
});
