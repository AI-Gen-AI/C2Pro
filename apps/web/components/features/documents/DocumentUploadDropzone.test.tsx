/**
 * Test Suite ID: S2-09
 * Roadmap Reference: S2-09 Document upload (drag-drop, PDF/XLSX/BC3, chunked)
 */
import { fireEvent, render, screen, waitFor } from "@/src/tests/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DocumentUploadDropzone } from "@/components/features/documents/DocumentUploadDropzone";

const uploadDocumentMock = vi.fn();
const getTokenMock = vi.fn();

vi.mock("@/lib/api", () => ({
  uploadDocument: (...args: unknown[]) => uploadDocumentMock(...args),
}));

vi.mock("@clerk/nextjs", () => ({
  useAuth: () => ({
    getToken: getTokenMock,
  }),
}));

function createFile(name: string, type: string, size = 1024): File {
  return new File([new Uint8Array(size)], name, { type });
}

describe("S2-09 - DocumentUploadDropzone", () => {
  afterEach(() => {
    uploadDocumentMock.mockReset();
    getTokenMock.mockReset();
  });

  it("rejects non-allowlisted extensions with explicit error", async () => {
    render(<DocumentUploadDropzone projectId="proj_demo_001" />);

    const dropzone = screen.getByRole("button", { name: /upload documents/i });
    fireEvent.drop(dropzone, {
      dataTransfer: {
        files: [createFile("malware.exe", "application/x-msdownload")],
      },
    });

    expect(
      await screen.findByText(
        /unsupported file type: \.exe\. allowed: pdf, xlsx, bc3/i,
      ),
    ).toBeInTheDocument();
    expect(uploadDocumentMock).not.toHaveBeenCalled();
  });

  it("updates drag state and aria labels during DnD lifecycle", () => {
    render(<DocumentUploadDropzone projectId="proj_demo_001" />);

    const dropzone = screen.getByRole("button", { name: /upload documents/i });

    fireEvent.dragEnter(dropzone);
    expect(dropzone).toHaveAttribute("data-drag-state", "active");
    expect(dropzone).toHaveAttribute("aria-label", "Drop files to upload");

    fireEvent.dragLeave(dropzone);
    expect(dropzone).toHaveAttribute("data-drag-state", "idle");
    expect(dropzone).toHaveAttribute("aria-label", "Upload documents");
  });

  it("supports keyboard file selection and announces status in the live region", () => {
    render(<DocumentUploadDropzone projectId="proj_demo_001" />);

    const browseButton = screen.getByRole("button", { name: /browse files/i });
    browseButton.focus();
    fireEvent.keyDown(browseButton, { key: "Enter" });

    expect(screen.getByRole("status")).toHaveTextContent(/file picker opened/i);
  });

  it("blocks oversize files with exact feedback", async () => {
    render(
      <DocumentUploadDropzone
        projectId="proj_demo_001"
        maxFileSizeBytes={10 * 1024 * 1024}
      />,
    );

    const dropzone = screen.getByRole("button", { name: /upload documents/i });
    fireEvent.drop(dropzone, {
      dataTransfer: {
        files: [createFile("large.pdf", "application/pdf", 11 * 1024 * 1024)],
      },
    });

    expect(
      await screen.findByText(/file exceeds 10mb limit: large\.pdf/i),
    ).toBeInTheDocument();
    expect(uploadDocumentMock).not.toHaveBeenCalled();
  });

  it("reports upload acceptance without implying backend processing is finished", async () => {
    uploadDocumentMock.mockResolvedValue({ id: "doc-1", task_id: "task-1" });
    getTokenMock.mockResolvedValue("fresh-token-123");
    const onUploadComplete = vi.fn();

    render(
      <DocumentUploadDropzone
        projectId="proj_live_001"
        onUploadComplete={onUploadComplete}
      />,
    );

    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, {
      target: {
        files: [createFile("contract.pdf", "application/pdf")],
      },
    });

    await waitFor(() => {
      expect(uploadDocumentMock).toHaveBeenCalledWith(
        "proj_live_001",
        expect.objectContaining({ name: "contract.pdf" }),
        "CONTRACT",
        { token: "fresh-token-123" },
      );
    });

    expect(
      await screen.findByText(
        /upload accepted for 1 file\(s\)\. backend processing is still required\./i,
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent(
      /upload request accepted/i,
    );
    expect(screen.queryByText(/upload complete!/i)).not.toBeInTheDocument();
    expect(onUploadComplete).toHaveBeenCalledTimes(1);
  });

  it("falls back to the shared auth store path when Clerk cannot supply a fresh token", async () => {
    uploadDocumentMock.mockResolvedValue({ id: "doc-1", task_id: "task-1" });
    getTokenMock.mockResolvedValue(null);

    render(<DocumentUploadDropzone projectId="proj_live_002" />);

    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, {
      target: {
        files: [createFile("contract.pdf", "application/pdf")],
      },
    });

    await waitFor(() => {
      expect(uploadDocumentMock).toHaveBeenCalledWith(
        "proj_live_002",
        expect.objectContaining({ name: "contract.pdf" }),
        "CONTRACT",
        undefined,
      );
    });
  });

  it("renders the upload surface with high-contrast styling for production readability", () => {
    render(<DocumentUploadDropzone projectId="proj_demo_001" />);

    expect(screen.getByTestId("document-upload-surface")).toHaveClass("bg-background");
    expect(screen.getByTestId("document-upload-surface")).toHaveClass("shadow-sm");
    expect(screen.getByTestId("document-upload-guidance")).toHaveTextContent(
      /files stay private to this project workspace/i,
    );

    const dropzone = screen.getByRole("button", { name: /upload documents/i });
    expect(dropzone).toHaveClass("bg-background");
    expect(dropzone).toHaveClass("shadow-sm");
    expect(dropzone).toHaveClass("text-foreground");
    expect(dropzone).toHaveClass("min-h-[260px]");
  });
});
