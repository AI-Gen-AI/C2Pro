import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@/src/tests/test-utils";

const pushMock = vi.fn();
const useProjectDocumentsMock = vi.fn();
const useProjectMock = vi.fn();
const mutateAsyncMock = vi.fn();
const useDeleteDocumentMock = vi.fn();
const apiClientPostMock = vi.fn();
const showToastMock = vi.fn();
const evaluateCoherenceMock = vi.fn();

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "proj_real_001" }),
  useRouter: () => ({
    push: pushMock,
  }),
}));

vi.mock("@/hooks/useProjectDocuments", () => ({
  useProjectDocuments: (...args: unknown[]) => useProjectDocumentsMock(...args),
}));

vi.mock("@/hooks/useProject", () => ({
  useProject: (...args: unknown[]) => useProjectMock(...args),
}));

vi.mock("@/hooks/useProjectCoherenceActions", () => ({
  useProjectCoherenceActions: () => ({
    evaluateCoherence: evaluateCoherenceMock,
    rerunAnalysis: vi.fn(),
    isEvaluating: false,
    isRerunningAnalysis: false,
  }),
}));

vi.mock("@/lib/api/generated/documents/documents", () => ({
  useDeleteDocumentEndpointApiV1DocumentsDocumentIdDelete: (...args: unknown[]) =>
    useDeleteDocumentMock(...args),
}));

vi.mock("@/lib/api/client", () => ({
  apiClient: {
    post: (...args: unknown[]) => apiClientPostMock(...args),
  },
}));

vi.mock("@/lib/ui/toast", () => ({
  showToast: (...args: unknown[]) => showToastMock(...args),
}));

vi.mock("@/components/features/analysis/AnalysisProgressTracker", () => ({
  AnalysisProgressTracker: ({ projectId }: { projectId: string }) => (
    <div>Analysis progress for {projectId}</div>
  ),
}));

vi.mock("@/components/features/documents/DocumentUploadDropzone", () => ({
  DocumentUploadDropzone: ({
    onUploadComplete,
    defaultType,
  }: {
    onUploadComplete?: () => void;
    defaultType?: string;
  }) => (
    <div>
      <div>Upload Dropzone</div>
      <div>Default upload type: {defaultType ?? "none"}</div>
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
    useProjectMock.mockReset();
    mutateAsyncMock.mockReset();
    useDeleteDocumentMock.mockReset();
    apiClientPostMock.mockReset();
    showToastMock.mockReset();
    evaluateCoherenceMock.mockReset();
    useProjectMock.mockReturnValue({
      data: {
        id: "proj_real_001",
        name: "Atlas Ridge",
      },
    });
    useDeleteDocumentMock.mockReturnValue({
      mutateAsync: (...args: unknown[]) => mutateAsyncMock(...args),
    });
  });

  it("shows the fetched project name instead of the raw route id in the page subtitle", () => {
    useProjectDocumentsMock.mockReturnValue({
      documents: [],
      loading: false,
      error: null,
      refetch: vi.fn(),
    });

    render(<ProjectDocumentsPage />);

    expect(screen.getByText("Project: Atlas Ridge")).toBeInTheDocument();
    expect(
      screen.queryByText("Project: proj_real_001"),
    ).not.toBeInTheDocument();
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

  it("shows analysis progress while documents are still processing", () => {
    useProjectDocumentsMock.mockReturnValue({
      documents: [
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

    expect(screen.getByText("Analysis progress for proj_real_001")).toBeInTheDocument();
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

    expect(screen.getByLabelText("Total Documents")).toHaveTextContent("3");
    expect(screen.getByLabelText("Analyzed")).toHaveTextContent("1");
    expect(screen.getByLabelText("Processing")).toHaveTextContent("1");
    expect(screen.getByText("Showing 3 of 3 documents")).toBeInTheDocument();
    expect(screen.getAllByText("Analyzed").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Processing").length).toBeGreaterThan(0);
    expect(screen.getByLabelText("Queued Or Errors")).toHaveTextContent("1");
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
    const uploadDialog = screen.getByRole("dialog", { name: /upload documents/i });
    expect(uploadDialog).toHaveClass("bg-card");
    expect(uploadDialog).toHaveClass("text-card-foreground");
    expect(uploadDialog).toHaveClass("shadow-2xl");
    expect(screen.getByTestId("documents-upload-dialog-shell")).toHaveClass("gap-5");
    expect(
      screen.getByText(/choose each file role before upload: contract, budget, or schedule/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/pdf, xlsx, bc3/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /finish upload/i }));

    await waitFor(() => expect(refetch).toHaveBeenCalledTimes(1));
    await waitFor(() =>
      expect(screen.queryByText("Upload Documents")).not.toBeInTheDocument(),
    );
  });

  it("opens upload with the checklist-selected document type", async () => {
    useProjectDocumentsMock.mockReturnValue({
      documents: [
        {
          id: "doc_contract_001",
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

    fireEvent.click(screen.getByRole("button", { name: /upload budget/i }));

    expect(screen.getByRole("dialog", { name: /upload documents/i })).toBeInTheDocument();
    expect(screen.getByText("Default upload type: budget")).toBeInTheDocument();
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

    fireEvent.click(screen.getByRole("button", { name: /delete contract\.pdf/i }));

    const deleteDialog = screen.getByRole("dialog", { name: /delete document/i });
    expect(deleteDialog).toHaveClass("bg-card");
    expect(deleteDialog).toHaveClass("shadow-2xl");
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

    fireEvent.click(screen.getByRole("button", { name: /delete contract\.pdf/i }));
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

    fireEvent.click(screen.getByRole("button", { name: /delete contract\.pdf/i }));
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

    fireEvent.click(screen.getByRole("button", { name: /delete contract\.pdf/i }));
    fireEvent.click(screen.getByRole("button", { name: /^delete$/i }));

    await waitFor(() =>
      expect(mutateAsyncMock).toHaveBeenCalledWith({ documentId: "doc_real_001" }),
    );
    expect(screen.getByText("Delete Document")).toBeInTheDocument();
    expect(refetch).not.toHaveBeenCalled();
  });

  it("separates filter controls from the results count to avoid dropdown overlap", () => {
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

    expect(screen.getByTestId("documents-filter-toolbar")).toHaveClass("flex-wrap");
    expect(screen.getByTestId("documents-results-summary")).toHaveTextContent(
      "Showing 1 of 1 documents",
    );
    expect(screen.getByTestId("documents-results-summary")).toHaveClass("border-t");
  });

  it("retries processing through the authenticated API client", async () => {
    const refetch = vi.fn();
    apiClientPostMock.mockResolvedValueOnce({ status: 202 });
    useProjectDocumentsMock.mockReturnValue({
      documents: [
        {
          id: "doc_error_001",
          name: "Budget.xlsx",
          type: "budget",
          fileSize: 1024,
          uploadedAt: new Date("2026-03-18T09:00:00Z"),
          status: "error",
        },
      ],
      loading: false,
      error: null,
      refetch,
    });

    render(<ProjectDocumentsPage />);

    fireEvent.click(screen.getByRole("button", { name: /retry processing budget\.xlsx/i }));

    await waitFor(() =>
      expect(apiClientPostMock).toHaveBeenCalledWith(
        "/projects/proj_real_001/documents/doc_error_001/reprocess",
      ),
    );
    await waitFor(() => expect(refetch).toHaveBeenCalledTimes(1));
  });

  it("shows a visible toast when retry processing fails", async () => {
    apiClientPostMock.mockRejectedValueOnce({
      response: { data: { detail: "worker unavailable" } },
    });
    useProjectDocumentsMock.mockReturnValue({
      documents: [
        {
          id: "doc_error_001",
          name: "Budget.xlsx",
          type: "budget",
          fileSize: 1024,
          uploadedAt: new Date("2026-03-18T09:00:00Z"),
          status: "error",
        },
      ],
      loading: false,
      error: null,
      refetch: vi.fn(),
    });

    render(<ProjectDocumentsPage />);

    fireEvent.click(screen.getByRole("button", { name: /retry processing budget\.xlsx/i }));

    await waitFor(() => expect(showToastMock).toHaveBeenCalledWith("worker unavailable"));
  });
});
