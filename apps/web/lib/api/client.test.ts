import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  apiClient,
  orvalApiClient,
  resetAuthFailureStateForTests,
} from "./client";

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
  afterEach(() => {
    mockedStore.clear.mockClear();
    mockedToast.mockClear();
  });

  beforeEach(() => {
    mockedEnv.APP_MODE = "production";
    resetAuthFailureStateForTests();
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
    const requestSpy = vi
      .spyOn(apiClient, "request")
      .mockResolvedValue({ data: { ok: true } });

    await expect(
      orvalApiClient<{ ok: boolean }>({
        url: "/documents",
        method: "GET",
      }),
    ).resolves.toEqual({ ok: true });

    expect(requestSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        url: "/documents",
        method: "GET",
      }),
    );
  });

  it("clears auth state and redirects to the canonical sign-in route on 401", async () => {
    const locationMock = { href: "/projects", pathname: "/projects" };
    Object.defineProperty(window, "location", {
      value: locationMock,
      writable: true,
      configurable: true,
    });

    const rejected = getRejectedHandler();

    await expect(rejected?.({ response: { status: 401 } })).rejects.toEqual({
      response: { status: 401 },
    });

    expect(mockedStore.clear).toHaveBeenCalledTimes(1);
    expect(mockedToast).toHaveBeenCalledWith("Sesión expirada o inválida");
    expect(window.location.href).toBe("/sign-in");
  });

  it("still redirects real workspace requests even when the demo environment is enabled", async () => {
    mockedEnv.APP_MODE = "demo";

    const locationMock = {
      href: "/projects/project-123",
      pathname: "/projects/project-123",
    };
    Object.defineProperty(window, "location", {
      value: locationMock,
      writable: true,
      configurable: true,
    });

    const rejected = getRejectedHandler();

    await expect(rejected?.({ response: { status: 401 } })).rejects.toEqual({
      response: { status: 401 },
    });

    expect(mockedStore.clear).toHaveBeenCalledTimes(1);
    expect(mockedToast).toHaveBeenCalledWith("Sesión expirada o inválida");
    expect(window.location.href).toBe("/sign-in");
  });

  it("does not redirect explicit demo routes on 401", async () => {
    mockedEnv.APP_MODE = "demo";

    const locationMock = {
      href: "/demo/projects/demo-001",
      pathname: "/demo/projects/demo-001",
    };
    Object.defineProperty(window, "location", {
      value: locationMock,
      writable: true,
      configurable: true,
    });

    const rejected = getRejectedHandler();

    await expect(rejected?.({ response: { status: 401 } })).rejects.toEqual({
      response: { status: 401 },
    });

    expect(mockedStore.clear).toHaveBeenCalledTimes(1);
    expect(mockedToast).not.toHaveBeenCalled();
    expect(window.location.href).toBe("/demo/projects/demo-001");
  });

  it("suppresses duplicate toasts and redirects when multiple 401s land together", async () => {
    const locationMock = { href: "/projects", pathname: "/projects" };
    Object.defineProperty(window, "location", {
      value: locationMock,
      writable: true,
      configurable: true,
    });

    const rejected = getRejectedHandler();

    await expect(rejected?.({ response: { status: 401 } })).rejects.toEqual({
      response: { status: 401 },
    });
    await expect(rejected?.({ response: { status: 401 } })).rejects.toEqual({
      response: { status: 401 },
    });

    expect(mockedStore.clear).toHaveBeenCalledTimes(2);
    expect(mockedToast).toHaveBeenCalledTimes(1);
    expect(window.location.href).toBe("/sign-in");
  });

  it("treats legacy auth aliases as auth pages and avoids redirect loops", async () => {
    const locationMock = { href: "/login", pathname: "/login" };
    Object.defineProperty(window, "location", {
      value: locationMock,
      writable: true,
      configurable: true,
    });

    const rejected = getRejectedHandler();

    await expect(rejected?.({ response: { status: 401 } })).rejects.toEqual({
      response: { status: 401 },
    });

    expect(mockedStore.clear).toHaveBeenCalledTimes(1);
    expect(mockedToast).not.toHaveBeenCalled();
    expect(window.location.href).toBe("/login");
  });
});
