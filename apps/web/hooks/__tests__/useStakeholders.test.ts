import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { waitFor, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createElement, type ReactNode } from "react";

import { useStakeholders } from "@/hooks/use-stakeholders";

const { getMock } = vi.hoisted(() => ({
  getMock: vi.fn(),
}));

vi.mock("@/lib/api/client", () => ({
  apiClient: {
    get: getMock,
  },
}));

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  return ({ children }: { children: ReactNode }) =>
    createElement(QueryClientProvider, { client: queryClient }, children);
}

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
      wrapper: createWrapper(),
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
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(getMock).not.toHaveBeenCalled();
    expect(result.current.data).toEqual([]);
  });
});
