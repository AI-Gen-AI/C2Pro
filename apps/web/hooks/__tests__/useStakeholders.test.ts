import { waitFor, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useStakeholders } from "@/hooks/use-stakeholders";
import { createTestWrapper } from "@/src/tests/test-utils";

const { getMock } = vi.hoisted(() => ({
  getMock: vi.fn(),
}));

vi.mock("@/lib/api/client", () => ({
  apiClient: {
    get: getMock,
  },
}));

describe("useStakeholders contract alignment", () => {
  beforeEach(() => {
    getMock.mockReset();
  });

  it("fetches stakeholders from the backend project route", async () => {
    getMock.mockResolvedValueOnce({
      data: [
        {
          id: "s-1",
          name: "Ana Ruiz",
          role: "PM",
          project_id: "proj-1",
          quadrant: "key_player",
          power_level: "high",
          interest_level: "high",
        },
      ],
    });

    const { result } = renderHook(() => useStakeholders("proj-1"), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(getMock).toHaveBeenCalledWith("/stakeholders/projects/proj-1");
    expect(result.current.data).toEqual([
      {
        id: "s-1",
        name: "Ana Ruiz",
        role: "PM",
        project_id: "proj-1",
        quadrant: "key_player",
        power_level: "high",
        interest_level: "high",
      },
    ]);
  });

  it("returns an empty list when no project id is provided", async () => {
    const { result } = renderHook(() => useStakeholders(undefined), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(getMock).not.toHaveBeenCalled();
    expect(result.current.data).toEqual([]);
  });
});
