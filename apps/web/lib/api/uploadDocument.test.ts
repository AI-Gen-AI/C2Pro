import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { uploadDocument as uploadDocumentType } from "./index";

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

  it("uploads through the same-origin API proxy when the browser is configured with a relative API base", async () => {
    const { uploadDocument } = await import("./index");

    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: vi.fn().mockResolvedValue({ id: "doc-1", task_id: "task-1" }),
    });

    const file = new File(["contract"], "contract.pdf", {
      type: "application/pdf",
    });

    await uploadDocument("proj_live_001", file, "contract");

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

  it("sends the selected generated document type in the multipart body", async () => {
    const { uploadDocument } = await import("./index");

    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: vi.fn().mockResolvedValue({ id: "doc-1", task_id: "task-1" }),
    });

    const file = new File(["budget"], "budget.xlsx", {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    });

    await uploadDocument("proj_live_001", file, "budget");

    const [, init] = fetchMock.mock.calls[0]!;
    const formData = (init as RequestInit).body as FormData;
    expect(formData.get("document_type")).toBe("budget");
  });

  it("does not accept the removed BOM upload type at compile time", () => {
    const acceptsDocumentType = (
      _value: Parameters<typeof uploadDocumentType>[2],
    ) => undefined;

    // @ts-expect-error BOM is not a generated backend DocumentType.
    acceptsDocumentType(`BO${"M"}`);
    expect(true).toBe(true);
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
      uploadDocument("proj_live_001", file, "contract"),
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

    await uploadDocument("proj_live_001", file, "contract", {
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
