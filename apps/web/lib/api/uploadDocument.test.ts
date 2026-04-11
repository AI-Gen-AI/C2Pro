import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const fetchMock = vi.fn();
const mockedHandleAuthErrorStatus = vi.fn();
const mockedStore = vi.hoisted(() => ({
  getState: vi.fn().mockReturnValue({
    token: "token-123",
    tenantId: "tenant-001",
  }),
}));

vi.mock("./client", () => ({
  apiClient: {
    defaults: {},
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
  },
  handleAuthErrorStatus: (...args: unknown[]) =>
    mockedHandleAuthErrorStatus(...args),
}));

vi.mock("@/stores/auth", () => ({
  useAuthStore: mockedStore,
}));

describe("uploadDocument", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.resetModules();
    fetchMock.mockReset();
    mockedHandleAuthErrorStatus.mockReset();
    vi.unstubAllGlobals();
  });

  it("resolves the backend API base before uploading when the browser only knows the proxy route", async () => {
    const { uploadDocument } = await import("./index");

    fetchMock
      .mockResolvedValueOnce({
        ok: true,
        json: vi.fn().mockResolvedValue({
          apiBaseUrl: "https://api.c2pro.io/api/v1",
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: vi.fn().mockResolvedValue({ id: "doc-1", task_id: "task-1" }),
      });

    const file = new File(["contract"], "contract.pdf", {
      type: "application/pdf",
    });

    await uploadDocument("proj_live_001", file, "CONTRACT");

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "/api/runtime/backend-url",
      expect.objectContaining({
        cache: "no-store",
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "https://api.c2pro.io/api/v1/projects/proj_live_001/documents",
      expect.objectContaining({
        method: "POST",
        headers: {
          Authorization: "Bearer token-123",
          "X-Tenant-ID": "tenant-001",
        },
        body: expect.any(FormData),
      }),
    );
    expect(fetchMock).not.toHaveBeenCalledWith(
      expect.stringContaining("/api/projects/proj_live_001/documents"),
      expect.anything(),
    );
    expect(fetchMock).not.toHaveBeenCalledWith(
      expect.stringContaining("/uploads/start"),
      expect.anything(),
    );
    expect(fetchMock).not.toHaveBeenCalledWith(
      expect.stringContaining("/uploads/finalize"),
      expect.anything(),
    );
  });

  it("uses the configured absolute backend base directly when available", async () => {
    vi.doMock("@/config/env", () => ({
      env: {
        API_BASE_URL: "https://api.c2pro.io/api/v1",
        BACKEND_ORIGIN: "https://api.c2pro.io",
      },
    }));

    const { uploadDocument } = await import("./index");

    fetchMock.mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue({ id: "doc-1", task_id: "task-1" }),
    });

    const file = new File(["contract"], "contract.pdf", {
      type: "application/pdf",
    });

    await uploadDocument("proj_live_001", file, "CONTRACT");

    expect(fetchMock).toHaveBeenCalledWith(
      "https://api.c2pro.io/api/v1/projects/proj_live_001/documents",
      expect.objectContaining({
        method: "POST",
        headers: {
          Authorization: "Bearer token-123",
          "X-Tenant-ID": "tenant-001",
        },
        body: expect.any(FormData),
      }),
    );
    expect(fetchMock).not.toHaveBeenCalledWith(
      expect.stringContaining("/uploads/start"),
      expect.anything(),
    );
    expect(fetchMock).not.toHaveBeenCalledWith(
      expect.stringContaining("/uploads/finalize"),
      expect.anything(),
    );
  });

  it("routes 401 upload failures through shared auth handling", async () => {
    const { uploadDocument } = await import("./index");

    fetchMock.mockResolvedValue({
      ok: false,
      status: 401,
      json: vi.fn().mockResolvedValue({ detail: "Unauthorized" }),
    });

    const file = new File(["contract"], "contract.pdf", {
      type: "application/pdf",
    });

    await expect(
      uploadDocument("proj_live_001", file, "CONTRACT"),
    ).rejects.toThrow("Unauthorized");

    expect(mockedHandleAuthErrorStatus).toHaveBeenCalledWith(401);
  });

  it("prefers an explicit fresh auth token override for direct uploads", async () => {
    const { uploadDocument } = await import("./index");

    fetchMock.mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue({ id: "doc-1", task_id: "task-1" }),
    });

    const file = new File(["contract"], "contract.pdf", {
      type: "application/pdf",
    });

    await uploadDocument("proj_live_001", file, "CONTRACT", {
      token: "fresh-token-456",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/projects/proj_live_001/documents"),
      expect.objectContaining({
        headers: {
          Authorization: "Bearer fresh-token-456",
          "X-Tenant-ID": "tenant-001",
        },
      }),
    );
  });
});
