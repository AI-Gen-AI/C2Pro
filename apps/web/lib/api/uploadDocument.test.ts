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

/** Mock the `/api/runtime/backend-url` lookup that precedes every upload. */
function mockBackendUrl(apiBaseUrl: string | null): void {
  fetchMock.mockResolvedValueOnce({
    ok: true,
    json: vi.fn().mockResolvedValue({ apiBaseUrl }),
  });
}

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

  it("uploads directly to the backend (bypassing the Vercel proxy) when an absolute backend URL is available", async () => {
    const { uploadDocument } = await import("./index");

    mockBackendUrl("https://backend.example/api/v1");
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: vi.fn().mockResolvedValue({ id: "doc-1", task_id: "task-1" }),
    });

    const file = new File(["contract"], "contract.pdf", {
      type: "application/pdf",
    });

    await uploadDocument("proj_live_001", file, "contract");

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/runtime/backend-url",
      expect.objectContaining({ cache: "no-store" }),
    );
    // The document POST must go straight to the backend, NOT the /api proxy,
    // so Vercel's ~4.5MB serverless body limit never applies.
    expect(fetchMock).toHaveBeenCalledWith(
      "https://backend.example/api/v1/projects/proj_live_001/documents",
      expect.objectContaining({
        method: "POST",
        headers: {
          Authorization: "Bearer token-123",
          "X-Tenant-ID": "tenant-001",
        },
        body: expect.any(FormData),
      }),
    );
  });

  it("falls back to the same-origin API proxy when no absolute backend URL is configured", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "/api");
    const { uploadDocument } = await import("./index");

    mockBackendUrl(null);
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
  });

  it("sends the selected generated document type in the multipart body", async () => {
    const { uploadDocument } = await import("./index");

    mockBackendUrl("https://backend.example/api/v1");
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: vi.fn().mockResolvedValue({ id: "doc-1", task_id: "task-1" }),
    });

    const file = new File(["budget"], "budget.xlsx", {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    });

    await uploadDocument("proj_live_001", file, "budget");

    // Call 0 is the backend-url lookup; call 1 is the document POST.
    const [, init] = fetchMock.mock.calls[1]!;
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

  it("surfaces a clear message when the server rejects the file as too large (413)", async () => {
    const { uploadDocument } = await import("./index");

    mockBackendUrl("https://backend.example/api/v1");
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 413,
      json: vi.fn().mockResolvedValue({}),
    });

    const file = new File(["x".repeat(10)], "big.pdf", {
      type: "application/pdf",
    });

    await expect(
      uploadDocument("proj_live_001", file, "contract"),
    ).rejects.toThrow(/too large/i);
  });

  it("routes 401 upload failures through shared auth handling", async () => {
    const { uploadDocument } = await import("./index");

    // Applies to both the backend-url lookup and the upload POST.
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

    mockBackendUrl("https://backend.example/api/v1");
    fetchMock.mockResolvedValueOnce({
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
