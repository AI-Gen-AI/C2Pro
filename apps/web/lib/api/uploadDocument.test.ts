import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { uploadDocument } from "./index";

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
    fetchMock.mockReset();
    mockedHandleAuthErrorStatus.mockReset();
    vi.unstubAllGlobals();
  });

  it("uses the real documents endpoint instead of the mock chunk-upload workflow", async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue({ id: "doc-1", task_id: "task-1" }),
    });

    const file = new File(["contract"], "contract.pdf", {
      type: "application/pdf",
    });

    await uploadDocument("proj_live_001", file, "CONTRACT");

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/projects/proj_live_001/documents",
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
});
