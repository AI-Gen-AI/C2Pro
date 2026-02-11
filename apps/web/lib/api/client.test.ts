import { describe, expect, it, vi } from "vitest";
import { apiClient } from "./client";

const mockedStore = vi.hoisted(() => ({
  getState: vi.fn().mockReturnValue({
    token: "token-123",
    tenantId: "tenant-001",
    clear: vi.fn(),
  }),
}));

vi.mock("@/stores/auth", () => ({
  useAuthStore: {
    getState: mockedStore.getState,
  },
}));

describe("apiClient auth interceptor", () => {
  it("attaches auth token and tenant id from auth store", async () => {
    const clientWithInterceptors = apiClient as unknown as {
      interceptors?: {
        request?: {
          handlers?: Array<{
            fulfilled?: (config: { headers?: Record<string, string> }) => Promise<{
              headers: Record<string, string>;
            }>;
          }>;
        };
      };
    };
    const handler =
      clientWithInterceptors.interceptors?.request?.handlers?.[0]?.fulfilled;
    expect(handler).toBeTypeOf("function");

    const config = await handler!({ headers: {} as Record<string, string> });
    expect(config.headers.Authorization).toBe("Bearer token-123");
    expect(config.headers["X-Tenant-ID"]).toBe("tenant-001");
  });
});
