/**
 * Test Suite ID: TASK-009
 * Utility Coverage: Shared frontend test helpers
 */
import { useQuery } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import {
  createMockSearchParams,
  createTestQueryClient,
  createTestWrapper,
} from "@/src/tests/test-utils";

describe("frontend test utilities", () => {
  it("creates a query client configured for deterministic tests", () => {
    const queryClient = createTestQueryClient();

    expect(queryClient.getDefaultOptions().queries?.retry).toBe(false);
  });

  it("creates reusable search params with stable getters", () => {
    const searchParams = createMockSearchParams({
      projectId: "proj-2",
      view: "matrix",
    });

    expect(searchParams.get("projectId")).toBe("proj-2");
    expect(searchParams.get("view")).toBe("matrix");
    expect(searchParams.get("missing")).toBeNull();
    expect(searchParams.toString()).toContain("projectId=proj-2");
  });

  it("provides a shared react-query wrapper for hook tests", async () => {
    const queryClient = createTestQueryClient();
    const wrapper = createTestWrapper({ queryClient });

    const { result } = renderHook(
      () =>
        useQuery({
          queryKey: ["ping"],
          queryFn: async () => "pong",
        }),
      { wrapper },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toBe("pong");
  });
});
