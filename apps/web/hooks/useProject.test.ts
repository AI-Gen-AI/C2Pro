/**
 * TS-TASK-013-PROJECT-CRUD-002: useProject hook project detail fetch coverage.
 */
import { waitFor, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useProject } from "@/hooks/useProject";
import { createTestWrapper } from "@/src/tests/test-utils";

const { getMock } = vi.hoisted(() => ({
  getMock: vi.fn(),
}));

vi.mock("@/lib/api/client", () => ({
  apiClient: {
    get: getMock,
  },
}));

describe("useProject contract alignment", () => {
  beforeEach(() => {
    getMock.mockReset();
  });

  it("fetches the requested project by id", async () => {
    getMock.mockResolvedValueOnce({
      data: { id: "proj-1", name: "Project One" },
    });

    const { result } = renderHook(() => useProject("proj-1"), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(getMock).toHaveBeenCalledWith("/projects/proj-1");
    expect(result.current.data).toEqual({ id: "proj-1", name: "Project One" });
  });

  it("stays idle when no project id is provided", async () => {
    const { result } = renderHook(() => useProject(null), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => expect(result.current.fetchStatus).toBe("idle"));

    expect(getMock).not.toHaveBeenCalled();
    expect(result.current.data).toBeUndefined();
  });
});
