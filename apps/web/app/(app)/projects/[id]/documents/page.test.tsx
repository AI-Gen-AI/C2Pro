import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@/src/tests/test-utils";

const pushMock = vi.fn();
const useProjectDocumentsMock = vi.fn();
const mutateAsyncMock = vi.fn();
const useDeleteDocumentMock = vi.fn();

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "proj_real_001" }),
  useRouter: () => ({
    push: pushMock,
  }),
}));

vi.mock("@/hooks/useProjectDocuments", () => ({
  useProjectDocuments: (...args: unknown[]) => useProjectDocumentsMock(...args),
}));

vi.mock("@/lib/api/generated/documents/documents", () => ({
  useDeleteDocumentEndpointApiV1DocumentsDocumentIdDelete: (...args: unknown[]) =>
    useDeleteDocumentMock(...args),
}));

vi.mock("@/components/features/documents/DocumentUploadDropzone", () => ({
  DocumentUploadDropzone: ({
    onUploadComplete,
  }: {
    onUploadComplete?: () => void;
  }) => (
    <div>
      <div>Upload Dropzone</div>
      <button type="button" onClick={onUploadComplete}>
        Finish Upload
      </button>
    </div>
  ),
}));

import ProjectDocumentsPage from "./page";

describe("ProjectDocumentsPage", () => {
  beforeEach(() => {
    pushMock.mockReset();
    useProjectDocumentsMock.mockReset();
    mutateAsyncMock.mockReset();
    useDeleteDocumentMock.mockReset();
    useDeleteDocumentMock.mockReturnValue({
      mutateAsync: (...args: unknown[]) => mutateAsyncMock(...args),
    });
  });

  it("shows an empty state when the backend returns no documents", () => {
    useProjectDocumentsMock.mockReturnValue({
      documents: [],
      loading: false,
      error: null,
      refetch: vi.fn(),
    });

    render(<ProjectDocumentsPage />);

    expect(
      screen.getByText("No documents found for this project"),
    ).toBeInTheDocument();
    expect(
      screen.queryByText("Contract Amendment v2.pdf"),
    ).not.toBeInTheDocument();
    expect(screen.getByText("Showing 0 of 0 documents")).toBeInTheDocument();
  });

  it("does not show the empty-project state when filters hide real backend documents", () => {
    useProjectDocumentsMock.mockReturnValue({
      documents: [
        {
          id: "doc_real_001",
          name: "Contract.pdf",
          type: "contract",
          fileSize: 2048,
          uploadedAt: new Date("2026-03-18T09:00:00Z"),
          status: "parsed",
        },
      ],
      loading: false,
      error: null,
      refetch: vi.fn(),
    });

    render(<ProjectDocumentsPage />);

    fireEvent.change(screen.getByPlaceholderText("Search documents..."), {
      target: { value: "no-match" },
    });

    expect(
      screen.queryByText("No documents found for this project"),
    ).not.toBeInTheDocument();
    expect(screen.getByText("No documents match the current filters")).toBeInTheDocument();
    expect(screen.getByText("Showing 0 of 1 documents")).toBeInTheDocument();
  });

  it("shows uploaded documents returned by the backend", () => {
    useProjectDocumentsMock.mockReturnValue({
      documents: [
        {
          id: "doc_real_001",
          name: "Contract.pdf",
          type: "contract",
          fileSize: 2048,
          uploadedAt: new Date("2026-03-18T09:00:00Z"),
          status: "parsed",
        },
        {
          id: "doc_real_002",
          name: "Schedule.xlsx",
          type: "schedule",
          fileSize: 4096,
          uploadedAt: new Date("2026-03-17T09:00:00Z"),
          status: "processing",
        },
      ],
      loading: false,
      error: null,
      refetch: vi.fn(),
    });

    render(<ProjectDocumentsPage />);

    expect(screen.getByText("Contract.pdf")).toBeInTheDocument();
    expect(screen.getByText("Schedule.xlsx")).toBeInTheDocument();
    expect(screen.getByText("Showing 2 of 2 documents")).toBeInTheDocument();
    expect(
      screen.queryByText("No documents found for this project"),
    ).not.toBeInTheDocument();
  });

  it("renders summary counters from backend document statuses", () => {
    useProjectDocumentsMock.mockReturnValue({
      documents: [
        {
          id: "doc_real_001",
          name: "Contract.pdf",
          type: "contract",
          fileSize: 2048,
          uploadedAt: new Date("2026-03-18T09:00:00Z"),
          status: "parsed",
        },
        {
          id: "doc_real_002",
          name: "Schedule.xlsx",
          type: "schedule",
          fileSize: 4096,
          uploadedAt: new Date("2026-03-17T09:00:00Z"),
          status: "processing",
        },
        {
          id: "doc_real_003",
          name: "Budget.csv",
          type: "budget",
          fileSize: 1024,
          uploadedAt: new Date("2026-03-16T09:00:00Z"),
          status: "failed",
        },
      ],
      loading: false,
      error: null,
      refetch: vi.fn(),
    });

    render(<ProjectDocumentsPage />);

    expect(screen.getByText("Total Documents")).toBeInTheDocument();
    expect(screen.getByText("Showing 3 of 3 documents")).toBeInTheDocument();
    expect(screen.getAllByText("Analyzed").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Processing").length).toBeGreaterThan(0);
    expect(screen.getByText("Errors")).toBeInTheDocument();
  });

  it("links each document row to the project evidence view with the selected document id", () => {
    useProjectDocumentsMock.mockReturnValue({
      documents: [
        {
          id: "doc_real_001",
          name: "Contract.pdf",
          type: "contract",
          fileSize: 2048,
          uploadedAt: new Date("2026-03-18T09:00:00Z"),
          status: "parsed",
        },
      ],
      loading: false,
      error: null,
      refetch: vi.fn(),
    });

    render(<ProjectDocumentsPage />);

    expect(screen.getByRole("link", { name: /contract\.pdf/i })).toHaveAttribute(
      "href",
      "/projects/proj_real_001/evidence?documentId=doc_real_001",
    );
  });

  it("shows the backend error state when documents fail to load", () => {
    useProjectDocumentsMock.mockReturnValue({
      documents: [],
      loading: false,
      error: new Error("boom"),
      refetch: vi.fn(),
    });

    render(<ProjectDocumentsPage />);

    expect(
      screen.getByText("Failed to load documents: boom"),
    ).toBeInTheDocument();
  });

  it("shows the loading state while documents are being fetched", () => {
    useProjectDocumentsMock.mockReturnValue({
      documents: [],
      loading: true,
      error: null,
      refetch: vi.fn(),
    });

    render(<ProjectDocumentsPage />);

    expect(screen.getByText("Loading documents...")).toBeInTheDocument();
  });

  it("navigates back to the project overview", () => {
    useProjectDocumentsMock.mockReturnValue({
      documents: [],
      loading: false,
      error: null,
      refetch: vi.fn(),
    });

    render(<ProjectDocumentsPage />);

    fireEvent.click(screen.getByRole("button", { name: /back to project/i }));

    expect(pushMock).toHaveBeenCalledWith("/projects/proj_real_001");
  });

  it("opens the upload dialog and refetches after a completed upload", async () => {
    const refetch = vi.fn();
    useProjectDocumentsMock.mockReturnValue({
      documents: [],
      loading: false,
      error: null,
      refetch,
    });

    render(<ProjectDocumentsPage />);

    fireEvent.click(screen.getByRole("button", { name: /upload document/i }));
    expect(screen.getByText("Upload Documents")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /finish upload/i }));

    await waitFor(() => expect(refetch).toHaveBeenCalledTimes(1));
    await waitFor(() =>
      expect(screen.queryByText("Upload Documents")).not.toBeInTheDocument(),
    );
  });

  it("opens the delete confirmation dialog for a selected document", () => {
    useProjectDocumentsMock.mockReturnValue({
      documents: [
        {
          id: "doc_real_001",
          name: "Contract.pdf",
          type: "contract",
          fileSize: 2048,
          uploadedAt: new Date("2026-03-18T09:00:00Z"),
          status: "parsed",
        },
      ],
      loading: false,
      error: null,
      refetch: vi.fn(),
    });

    render(<ProjectDocumentsPage />);

    fireEvent.click(screen.getAllByRole("button")[2]);

    expect(screen.getByText("Delete Document")).toBeInTheDocument();
    expect(
      screen.getByText(/are you sure you want to delete "Contract\.pdf"\?/i),
    ).toBeInTheDocument();
  });

  it("closes the delete confirmation dialog without deleting when cancel is pressed", async () => {
    useProjectDocumentsMock.mockReturnValue({
      documents: [
        {
          id: "doc_real_001",
          name: "Contract.pdf",
          type: "contract",
          fileSize: 2048,
          uploadedAt: new Date("2026-03-18T09:00:00Z"),
          status: "parsed",
        },
      ],
      loading: false,
      error: null,
      refetch: vi.fn(),
    });

    render(<ProjectDocumentsPage />);

    fireEvent.click(screen.getAllByRole("button")[2]);
    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));

    await waitFor(() =>
      expect(screen.queryByText("Delete Document")).not.toBeInTheDocument(),
    );
    expect(mutateAsyncMock).not.toHaveBeenCalled();
  });

  it("deletes the document and refetches the list after confirmation", async () => {
    const refetch = vi.fn();
    mutateAsyncMock.mockResolvedValueOnce(undefined);
    useProjectDocumentsMock.mockReturnValue({
      documents: [
        {
          id: "doc_real_001",
          name: "Contract.pdf",
          type: "contract",
          fileSize: 2048,
          uploadedAt: new Date("2026-03-18T09:00:00Z"),
          status: "parsed",
        },
      ],
      loading: false,
      error: null,
      refetch,
    });

    render(<ProjectDocumentsPage />);

    fireEvent.click(screen.getAllByRole("button")[2]);
    fireEvent.click(screen.getByRole("button", { name: /^delete$/i }));

    await waitFor(() =>
      expect(mutateAsyncMock).toHaveBeenCalledWith({ documentId: "doc_real_001" }),
    );
    await waitFor(() => expect(refetch).toHaveBeenCalledTimes(1));
  });

  it("keeps the delete dialog open and skips refetch when deletion fails", async () => {
    const refetch = vi.fn();
    mutateAsyncMock.mockRejectedValueOnce(new Error("Delete failed"));
    useProjectDocumentsMock.mockReturnValue({
      documents: [
        {
          id: "doc_real_001",
          name: "Contract.pdf",
          type: "contract",
          fileSize: 2048,
          uploadedAt: new Date("2026-03-18T09:00:00Z"),
          status: "parsed",
        },
      ],
      loading: false,
      error: null,
      refetch,
    });

    render(<ProjectDocumentsPage />);

    fireEvent.click(screen.getAllByRole("button")[2]);
    fireEvent.click(screen.getByRole("button", { name: /^delete$/i }));

    await waitFor(() =>
      expect(mutateAsyncMock).toHaveBeenCalledWith({ documentId: "doc_real_001" }),
    );
    expect(screen.getByText("Delete Document")).toBeInTheDocument();
    expect(refetch).not.toHaveBeenCalled();
  });
});
