import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mockedAxiosClient = vi.hoisted(() => {
  const requestHandlers: Array<{
    fulfilled?: (config: { headers?: Record<string, string> }) => unknown;
  }> = [];
  const responseHandlers: Array<{
    rejected?: (error: { response?: { status?: number } }) => Promise<never>;
  }> = [];

  return {
    request: vi.fn(),
    interceptors: {
      request: {
        handlers: requestHandlers,
        use: vi.fn(
          (fulfilled: (config: { headers?: Record<string, string> }) => unknown) => {
            requestHandlers.push({ fulfilled });
            return requestHandlers.length - 1;
          },
        ),
      },
      response: {
        handlers: responseHandlers,
        use: vi.fn(
          (
            _fulfilled: ((response: unknown) => unknown) | undefined,
            rejected: ((error: { response?: { status?: number } }) => Promise<never>) | undefined,
          ) => {
            responseHandlers.push({ rejected });
            return responseHandlers.length - 1;
          },
        ),
      },
    },
  };
});

const mockedAxiosModule = vi.hoisted(() => ({
  create: vi.fn(() => mockedAxiosClient),
}));

const mockedStore = vi.hoisted(() => ({
  clear: vi.fn(),
  getState: vi.fn().mockReturnValue({
    token: "token-123",
    tenantId: "tenant-001",
    clear: undefined as unknown,
  }),
}));

const mockedEnv = vi.hoisted(() => ({
  APP_MODE: "production" as "production" | "demo",
}));

const mockedToast = vi.hoisted(() => vi.fn());

vi.mock("axios", () => ({
  default: mockedAxiosModule,
}));

vi.mock("axios/dist/browser/axios.cjs", () => ({
  default: mockedAxiosModule,
}));

import {
  apiClient,
  orvalApiClient,
  resetAuthFailureStateForTests,
  setBrowserLocationAdapterForTests,
} from "./client";

mockedStore.getState.mockReturnValue({
  token: "token-123",
  tenantId: "tenant-001",
  clear: mockedStore.clear,
});

vi.mock("@/stores/auth", () => ({
  useAuthStore: {
    getState: mockedStore.getState,
  },
}));

vi.mock("@/config/env", () => ({
  env: mockedEnv,
}));

vi.mock("@/lib/ui/toast", () => ({
  showToast: mockedToast,
}));

describe("apiClient auth interceptor", () => {
  let redirectSpy: () => void;
  let currentPathname = "/";

  afterEach(() => {
    mockedStore.clear.mockClear();
    mockedToast.mockClear();
    setBrowserLocationAdapterForTests(null);
  });

  beforeEach(() => {
    mockedEnv.APP_MODE = "production";
    resetAuthFailureStateForTests();
    currentPathname = "/";
    redirectSpy = vi.fn();
    setBrowserLocationAdapterForTests({
      getPathname: () => currentPathname,
      redirectToSignIn: redirectSpy,
    });
  });

  const getRejectedHandler = () => {
    const clientWithInterceptors = apiClient as unknown as {
      interceptors?: {
        response?: {
          handlers?: Array<{
            rejected?: (error: {
              response?: { status?: number };
            }) => Promise<never>;
          }>;
        };
      };
    };

    return clientWithInterceptors.interceptors?.response?.handlers?.[0]
      ?.rejected;
  };

  it("attaches auth token and tenant id from auth store", async () => {
    const clientWithInterceptors = apiClient as unknown as {
      interceptors?: {
        request?: {
          handlers?: Array<{
            fulfilled?: (config: {
              headers?: Record<string, string>;
            }) => Promise<{
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

  it("exports a callable Orval mutator that delegates through the shared axios client", async () => {
    mockedAxiosClient.request.mockResolvedValue({ data: { ok: true } });

    await expect(
      orvalApiClient<{ ok: boolean }>({
        url: "/documents",
        method: "GET",
      }),
    ).resolves.toEqual({ ok: true });

    expect(mockedAxiosClient.request).toHaveBeenCalledWith(
      expect.objectContaining({
        url: "/documents",
        method: "GET",
      }),
    );
  });

  it("normalizes generated /api/v1 paths before delegating through the shared axios client", async () => {
    mockedAxiosClient.request.mockResolvedValue({ data: { ok: true } });

    await expect(
      orvalApiClient<{ ok: boolean }>({
        url: "/api/v1/projects/proj-1/alerts",
        method: "GET",
      }),
    ).resolves.toEqual({ ok: true });

    expect(mockedAxiosClient.request).toHaveBeenCalledWith(
      expect.objectContaining({
        url: "/projects/proj-1/alerts",
        method: "GET",
      }),
    );
  });

  it("clears auth state and redirects to the canonical sign-in route on 401", async () => {
    currentPathname = "/projects";

    const rejected = getRejectedHandler();

    await expect(rejected?.({ response: { status: 401 } })).rejects.toEqual({
      response: { status: 401 },
    });

    expect(mockedStore.clear).toHaveBeenCalledTimes(1);
    expect(mockedToast).toHaveBeenCalledWith("Session expired or invalid");
    expect(redirectSpy).toHaveBeenCalledTimes(1);
  });

  it("still redirects real workspace requests even when the demo environment is enabled", async () => {
    mockedEnv.APP_MODE = "demo";
    currentPathname = "/projects/project-123";

    const rejected = getRejectedHandler();

    await expect(rejected?.({ response: { status: 401 } })).rejects.toEqual({
      response: { status: 401 },
    });

    expect(mockedStore.clear).toHaveBeenCalledTimes(1);
    expect(mockedToast).toHaveBeenCalledWith("Session expired or invalid");
    expect(redirectSpy).toHaveBeenCalledTimes(1);
  });

  it("does not redirect explicit demo routes on 401", async () => {
    mockedEnv.APP_MODE = "demo";
    currentPathname = "/demo/projects/demo-001";

    const rejected = getRejectedHandler();

    await expect(rejected?.({ response: { status: 401 } })).rejects.toEqual({
      response: { status: 401 },
    });

    expect(mockedStore.clear).toHaveBeenCalledTimes(1);
    expect(mockedToast).not.toHaveBeenCalled();
    expect(redirectSpy).not.toHaveBeenCalled();
  });

  it("suppresses duplicate toasts and redirects when multiple 401s land together", async () => {
    currentPathname = "/projects";

    const rejected = getRejectedHandler();

    await expect(rejected?.({ response: { status: 401 } })).rejects.toEqual({
      response: { status: 401 },
    });
    await expect(rejected?.({ response: { status: 401 } })).rejects.toEqual({
      response: { status: 401 },
    });

    expect(mockedStore.clear).toHaveBeenCalledTimes(2);
    expect(mockedToast).toHaveBeenCalledTimes(1);
    expect(redirectSpy).toHaveBeenCalledTimes(1);
  });

  it("treats legacy auth aliases as auth pages and avoids redirect loops", async () => {
    currentPathname = "/login";

    const rejected = getRejectedHandler();

    await expect(rejected?.({ response: { status: 401 } })).rejects.toEqual({
      response: { status: 401 },
    });

    expect(mockedStore.clear).toHaveBeenCalledTimes(1);
    expect(mockedToast).not.toHaveBeenCalled();
    expect(redirectSpy).not.toHaveBeenCalled();
  });
});
