import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useProjectDocuments } from "@/hooks/useProjectDocuments";
import { createTestWrapper } from "@/src/tests/test-utils";

const { getProjectDocumentsMock } = vi.hoisted(() => ({
  getProjectDocumentsMock: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  getProjectDocuments: (...args: unknown[]) => getProjectDocumentsMock(...args),
}));

describe("useProjectDocuments", () => {
  beforeEach(() => {
    getProjectDocumentsMock.mockReset();
    vi.useRealTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("returns an empty stable state when project id is missing", async () => {
    const { result } = renderHook(() => useProjectDocuments(null), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(getProjectDocumentsMock).not.toHaveBeenCalled();
    expect(result.current.documents).toEqual([]);
    expect(result.current.error).toBeNull();
  });

  it("transforms backend documents into document info records", async () => {
    getProjectDocumentsMock.mockResolvedValueOnce([
      {
        id: "doc-1",
        filename: "Contract.pdf",
        document_type: "CONTRACT",
        status: "parsed",
        uploaded_at: "2026-03-18T09:00:00Z",
        file_size_bytes: 2048,
      },
      {
        id: "doc-2",
        filename: "Schedule.xlsx",
        document_type: "schedule",
        status: "processing",
        uploaded_at: "2026-03-19T09:00:00Z",
        file_size_bytes: 4096,
      },
    ]);

    const { result } = renderHook(() => useProjectDocuments("proj-1"), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(getProjectDocumentsMock).toHaveBeenCalledWith("proj-1");
    expect(result.current.documents[0]).toMatchObject({
      id: "doc-1",
      name: "Contract.pdf",
      type: "contract",
      extension: "pdf",
      fileSize: 2048,
      status: "parsed",
    });
    expect(result.current.documents[1]).toMatchObject({
      id: "doc-2",
      name: "Schedule.xlsx",
      type: "schedule",
      extension: "xlsx",
      fileSize: 4096,
      status: "processing",
    });
  });

  it("keeps generated budget and other document types honest in the register", async () => {
    getProjectDocumentsMock.mockResolvedValueOnce([
      {
        id: "doc-budget",
        filename: "Budget.xlsx",
        document_type: "budget",
        status: "parsed",
        uploaded_at: "2026-03-18T09:00:00Z",
        file_size_bytes: 2048,
      },
      {
        id: "doc-other",
        filename: "Other.pdf",
        document_type: "other",
        status: "parsed",
        uploaded_at: "2026-03-19T09:00:00Z",
        file_size_bytes: 1024,
      },
    ]);

    const { result } = renderHook(() => useProjectDocuments("proj-budget"), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.documents).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ id: "doc-budget", type: "budget" }),
        expect.objectContaining({ id: "doc-other", type: "other" }),
      ]),
    );
  });

  it("falls back unknown types and extensions to safe defaults", async () => {
    getProjectDocumentsMock.mockResolvedValueOnce([
      {
        id: "doc-3",
        filename: "Spec.unknown",
        document_type: "MYSTERY",
        status: "queued",
        uploaded_at: "2026-03-20T09:00:00Z",
        file_size_bytes: 128,
      },
    ]);

    const { result } = renderHook(() => useProjectDocuments("proj-2"), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.documents[0]).toMatchObject({
      type: "other",
      extension: "pdf",
      status: "queued",
    });
  });

  it("surfaces fetch failures", async () => {
    getProjectDocumentsMock.mockRejectedValueOnce(new Error("documents down"));

    const { result } = renderHook(() => useProjectDocuments("proj-3"), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.documents).toEqual([]);
    expect(result.current.error?.message).toBe("documents down");
  });

  it("refetch reloads the project documents", async () => {
    getProjectDocumentsMock
      .mockResolvedValueOnce([
        {
          id: "doc-1",
          filename: "One.pdf",
          document_type: "contract",
          status: "parsed",
          uploaded_at: "2026-03-18T09:00:00Z",
          file_size_bytes: 2048,
        },
      ])
      .mockResolvedValueOnce([
        {
          id: "doc-2",
          filename: "Two.pdf",
          document_type: "contract",
          status: "parsed",
          uploaded_at: "2026-03-19T09:00:00Z",
          file_size_bytes: 1024,
        },
      ]);

    const { result } = renderHook(() => useProjectDocuments("proj-4"), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => expect(result.current.loading).toBe(false));
    await result.current.refetch();

    await waitFor(() =>
      expect(result.current.documents[0]).toMatchObject({ id: "doc-2", name: "Two.pdf" }),
    );
    expect(getProjectDocumentsMock).toHaveBeenCalledTimes(2);
  });

  it("polls while documents are in flight and stops after analysis completes", async () => {
    vi.useFakeTimers();
    getProjectDocumentsMock
      .mockResolvedValueOnce([
        {
          id: "doc-processing",
          filename: "Schedule.xlsx",
          document_type: "schedule",
          status: "processing",
          uploaded_at: "2026-03-19T09:00:00Z",
          file_size_bytes: 4096,
        },
      ])
      .mockResolvedValueOnce([
        {
          id: "doc-processing",
          filename: "Schedule.xlsx",
          document_type: "schedule",
          status: "analyzed",
          uploaded_at: "2026-03-19T09:00:00Z",
          file_size_bytes: 4096,
        },
      ]);

    const { result } = renderHook(() => useProjectDocuments("proj-polling"), {
      wrapper: createTestWrapper(),
    });

    await vi.waitFor(() =>
      expect(result.current.documents[0]?.status).toBe("processing"),
    );

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });
    await vi.waitFor(() =>
      expect(result.current.documents[0]?.status).toBe("analyzed"),
    );
    expect(getProjectDocumentsMock).toHaveBeenCalledTimes(2);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });
    expect(getProjectDocumentsMock).toHaveBeenCalledTimes(2);
  });

  it("carries the backend lifecycle state alongside the polling status", async () => {
    getProjectDocumentsMock.mockResolvedValueOnce([
      {
        id: "doc-pending",
        filename: "Contract.pdf",
        document_type: "contract",
        status: "processing",
        lifecycle_status: "analysis_pending",
        uploaded_at: "2026-03-19T09:00:00Z",
        file_size_bytes: 2048,
      },
      {
        id: "doc-legacy",
        filename: "Budget.xlsx",
        document_type: "budget",
        status: "parsed",
        uploaded_at: "2026-03-19T09:00:00Z",
        file_size_bytes: 1024,
      },
    ]);

    const { result } = renderHook(() => useProjectDocuments("proj-lifecycle"), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => expect(result.current.documents).toHaveLength(2));
    expect(result.current.documents[0]).toMatchObject({
      status: "processing",
      lifecycleStatus: "analysis_pending",
    });
    expect(result.current.documents[1]?.lifecycleStatus).toBeUndefined();
  });

  it("carries retryable, review count and review item id through from the backend (#712)", async () => {
    getProjectDocumentsMock.mockResolvedValueOnce([
      {
        id: "doc-review",
        filename: "Contract.pdf",
        document_type: "contract",
        status: "processing",
        status_detail: "Analysis completed and is waiting for a human review decision.",
        lifecycle_status: "review_required",
        retryable: false,
        review_count: 1,
        review_item_id: "11111111-1111-1111-1111-111111111111",
        uploaded_at: "2026-03-19T09:00:00Z",
        file_size_bytes: 2048,
      },
    ]);

    const { result } = renderHook(() => useProjectDocuments("proj-review"), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => expect(result.current.documents).toHaveLength(1));
    expect(result.current.documents[0]).toMatchObject({
      lifecycleStatus: "review_required",
      statusDetail: "Analysis completed and is waiting for a human review decision.",
      retryable: false,
      reviewCount: 1,
      reviewItemId: "11111111-1111-1111-1111-111111111111",
    });
  });

  it("stops polling a document paused for human review, even though its legacy status still reads processing (#712)", async () => {
    vi.useFakeTimers();
    getProjectDocumentsMock.mockResolvedValue([
      {
        id: "doc-review",
        filename: "Contract.pdf",
        document_type: "contract",
        status: "processing",
        lifecycle_status: "review_required",
        uploaded_at: "2026-03-19T09:00:00Z",
        file_size_bytes: 2048,
      },
    ]);

    const { result } = renderHook(() => useProjectDocuments("proj-review-poll"), {
      wrapper: createTestWrapper(),
    });

    await vi.waitFor(() =>
      expect(result.current.documents[0]?.lifecycleStatus).toBe("review_required"),
    );
    expect(getProjectDocumentsMock).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });
    expect(getProjectDocumentsMock).toHaveBeenCalledTimes(1);
  });

  it("stops polling an exhausted, retryable analysis attempt (#712)", async () => {
    vi.useFakeTimers();
    getProjectDocumentsMock.mockResolvedValue([
      {
        id: "doc-retry",
        filename: "Contract.pdf",
        document_type: "contract",
        status: "processing",
        lifecycle_status: "failed_retryable",
        retryable: true,
        uploaded_at: "2026-03-19T09:00:00Z",
        file_size_bytes: 2048,
      },
    ]);

    const { result } = renderHook(() => useProjectDocuments("proj-retry-poll"), {
      wrapper: createTestWrapper(),
    });

    await vi.waitFor(() =>
      expect(result.current.documents[0]?.lifecycleStatus).toBe("failed_retryable"),
    );
    expect(getProjectDocumentsMock).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });
    expect(getProjectDocumentsMock).toHaveBeenCalledTimes(1);
  });

  it("stops polling a durable rejection, even though its legacy status still reads error (#712)", async () => {
    vi.useFakeTimers();
    getProjectDocumentsMock.mockResolvedValue([
      {
        id: "doc-rejected",
        filename: "Contract.pdf",
        document_type: "contract",
        status: "error",
        lifecycle_status: "needs_changes",
        uploaded_at: "2026-03-19T09:00:00Z",
        file_size_bytes: 2048,
      },
    ]);

    const { result } = renderHook(() => useProjectDocuments("proj-rejected-poll"), {
      wrapper: createTestWrapper(),
    });

    await vi.waitFor(() =>
      expect(result.current.documents[0]?.lifecycleStatus).toBe("needs_changes"),
    );

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });
    expect(getProjectDocumentsMock).toHaveBeenCalledTimes(1);
  });
});
