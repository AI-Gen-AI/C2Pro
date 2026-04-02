/**
 * Test Suite ID: TASK-021
 * Service Coverage: shared fetch helper mirrors browser auth headers and auth-failure handling.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";

const handleAuthErrorStatus = vi.fn();
const getState = vi.fn();

vi.mock("@/lib/api/client", () => ({
  handleAuthErrorStatus: (status: number | undefined) =>
    handleAuthErrorStatus(status),
}));

vi.mock("@/stores/auth", () => ({
  useAuthStore: {
    getState: () => getState(),
  },
}));

describe("fetchApiJson", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    fetchMock.mockReset();
    handleAuthErrorStatus.mockReset();
    getState.mockReset();
    getState.mockReturnValue({ token: null, tenantId: null });
    vi.stubGlobal("fetch", fetchMock);
  });

  it("adds auth and tenant headers for browser-side requests", async () => {
    getState.mockReturnValue({
      token: "token-123",
      tenantId: "tenant-uuid-1",
    });
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ items: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const { fetchApiJson } = await import("@/lib/api/services/http");

    await fetchApiJson("projects");

    expect(fetchMock).toHaveBeenCalledWith("/api/v1/projects", {
      headers: {
        authorization: "Bearer token-123",
        "x-tenant-id": "tenant-uuid-1",
      },
    });
  });

  it("routes browser-side auth failures through the canonical status handler", async () => {
    getState.mockReturnValue({
      token: "token-123",
      tenantId: "tenant-uuid-1",
    });
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          detail: "Not authenticated",
          reason_code: "missing_or_invalid_token",
        }),
        {
          status: 401,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );

    const { fetchApiJson } = await import("@/lib/api/services/http");

    await expect(fetchApiJson("projects")).rejects.toThrow("Not authenticated");
    expect(handleAuthErrorStatus).toHaveBeenCalledWith(401);
  });

  it("does not inject browser auth headers during server-side loading", async () => {
    getState.mockReturnValue({
      token: "token-123",
      tenantId: "tenant-uuid-1",
    });
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ items: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const { fetchApiJson } = await import("@/lib/api/services/http");

    await fetchApiJson("projects", { server: true });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/projects",
      {},
    );
  });
});
