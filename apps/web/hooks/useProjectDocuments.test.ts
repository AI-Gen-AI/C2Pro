import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useProjectDocuments } from "@/hooks/useProjectDocuments";

const { getProjectDocumentsMock } = vi.hoisted(() => ({
  getProjectDocumentsMock: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  getProjectDocuments: (...args: unknown[]) => getProjectDocumentsMock(...args),
}));

describe("useProjectDocuments", () => {
  beforeEach(() => {
    getProjectDocumentsMock.mockReset();
  });

  it("returns an empty stable state when project id is missing", async () => {
    const { result } = renderHook(() => useProjectDocuments(null));

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

    const { result } = renderHook(() => useProjectDocuments("proj-1"));

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

    const { result } = renderHook(() => useProjectDocuments("proj-budget"));

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

    const { result } = renderHook(() => useProjectDocuments("proj-2"));

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.documents[0]).toMatchObject({
      type: "other",
      extension: "pdf",
      status: "queued",
    });
  });

  it("surfaces fetch failures", async () => {
    getProjectDocumentsMock.mockRejectedValueOnce(new Error("documents down"));

    const { result } = renderHook(() => useProjectDocuments("proj-3"));

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

    const { result } = renderHook(() => useProjectDocuments("proj-4"));

    await waitFor(() => expect(result.current.loading).toBe(false));
    await result.current.refetch();

    await waitFor(() =>
      expect(result.current.documents[0]).toMatchObject({ id: "doc-2", name: "Two.pdf" }),
    );
    expect(getProjectDocumentsMock).toHaveBeenCalledTimes(2);
  });
});
