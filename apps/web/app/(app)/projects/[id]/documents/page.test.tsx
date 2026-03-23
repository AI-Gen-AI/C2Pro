import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@/src/tests/test-utils";

const pushMock = vi.fn();
const useProjectDocumentsMock = vi.fn();

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "proj_real_001" }),
  useRouter: () => ({
    push: pushMock,
  }),
}));

vi.mock("@/hooks/useProjectDocuments", () => ({
  useProjectDocuments: (...args: unknown[]) => useProjectDocumentsMock(...args),
}));

vi.mock("@/components/features/documents/DocumentUploadDropzone", () => ({
  DocumentUploadDropzone: () => <div>Upload Dropzone</div>,
}));

import ProjectDocumentsPage from "./page";

describe("ProjectDocumentsPage", () => {
  beforeEach(() => {
    pushMock.mockReset();
    useProjectDocumentsMock.mockReset();
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
});
