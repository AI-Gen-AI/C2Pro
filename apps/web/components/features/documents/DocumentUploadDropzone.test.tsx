/**
 * Test Suite ID: S2-09
 * Roadmap Reference: S2-09 Document upload (drag-drop, PDF/XLSX/BC3, chunked)
 */
import { fireEvent, render, screen, waitFor } from "@/src/tests/test-utils";
import userEvent from "@testing-library/user-event";
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
        /unsupported file type: \.exe\. allowed: pdf, docx, xlsx, bc3/i,
      ),
    ).toBeInTheDocument();
    expect(uploadDocumentMock).not.toHaveBeenCalled();
  });

  it("stages dropped files with extension-based document type defaults", async () => {
    render(<DocumentUploadDropzone projectId="proj_demo_001" />);

    const dropzone = screen.getByRole("button", { name: /upload documents/i });
    fireEvent.drop(dropzone, {
      dataTransfer: {
        files: [
          createFile("contract.pdf", "application/pdf"),
          createFile("budget.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
          createFile("schedule.bc3", "application/octet-stream"),
        ],
      },
    });

    expect(await screen.findByText("contract.pdf")).toBeInTheDocument();
    expect(screen.getByText("budget.xlsx")).toBeInTheDocument();
    expect(screen.getByText("schedule.bc3")).toBeInTheDocument();
    expect(screen.getByLabelText(/document type for contract\.pdf/i)).toHaveTextContent("Contract");
    expect(screen.getByLabelText(/document type for budget\.xlsx/i)).toHaveTextContent("Budget");
    expect(screen.getByLabelText(/document type for schedule\.bc3/i)).toHaveTextContent("Budget");
    expect(uploadDocumentMock).not.toHaveBeenCalled();
  });

  it("stages and uploads a DOCX contract supported by the backend", async () => {
    uploadDocumentMock.mockResolvedValue({ id: "doc-docx", task_id: "task-docx" });
    getTokenMock.mockResolvedValue("fresh-token-123");
    render(<DocumentUploadDropzone projectId="proj_docx" />);

    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    expect(input).toHaveAttribute("accept", ".pdf,.docx,.xlsx,.bc3");
    fireEvent.change(input, {
      target: {
        files: [createFile(
          "contract.docx",
          "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )],
      },
    });

    expect(await screen.findByText("contract.docx")).toBeInTheDocument();
    expect(screen.getByLabelText(/document type for contract\.docx/i)).toHaveTextContent("Contract");
    fireEvent.click(screen.getByRole("button", { name: /upload 1 file/i }));

    await waitFor(() => {
      expect(uploadDocumentMock).toHaveBeenCalledWith(
        "proj_docx",
        expect.objectContaining({ name: "contract.docx" }),
        "contract",
        { token: "fresh-token-123" },
      );
    });
  });

  it("uploads a DOCX technical specification under its explicit document type", async () => {
    const user = userEvent.setup();
    uploadDocumentMock.mockResolvedValue({ id: "doc-spec", task_id: "task-spec" });
    getTokenMock.mockResolvedValue("fresh-token-123");
    render(<DocumentUploadDropzone projectId="proj_docx" />);

    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, {
      target: {
        files: [createFile(
          "technical-specification.docx",
          "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )],
      },
    });

    const type = await screen.findByLabelText(/document type for technical-specification\.docx/i);
    await user.click(type);
    await user.click(await screen.findByRole("option", { name: "Technical specification" }));
    await user.click(screen.getByRole("button", { name: /upload 1 file/i }));

    await waitFor(() => {
      expect(uploadDocumentMock).toHaveBeenCalledWith(
        "proj_docx",
        expect.objectContaining({ name: "technical-specification.docx" }),
        "technical_spec",
        { token: "fresh-token-123" },
      );
    });
  });

  it("rejects an entire mixed batch if any DOCX is assigned to Budget", async () => {
    const user = userEvent.setup();
    render(<DocumentUploadDropzone projectId="proj_docx" />);

    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, {
      target: {
        files: [
          createFile("valid-contract.pdf", "application/pdf"),
          createFile(
            "invalid-budget.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
          ),
        ],
      },
    });

    expect(await screen.findByText("valid-contract.pdf")).toBeInTheDocument();
    const type = await screen.findByLabelText(/document type for invalid-budget\.docx/i);
    await user.click(type);
    await user.click(await screen.findByRole("option", { name: "Budget" }));
    await user.click(screen.getByRole("button", { name: /upload 2 files/i }));

    expect(await screen.findByText(/DOCX cannot be uploaded as budget/i)).toBeInTheDocument();
    expect(uploadDocumentMock).not.toHaveBeenCalled();
    expect(getTokenMock).not.toHaveBeenCalled();
  });

  it("refuses DOCX as a structured schedule before any upload request", async () => {
    const user = userEvent.setup();
    render(<DocumentUploadDropzone projectId="proj_docx" />);

    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, {
      target: {
        files: [createFile(
          "schedule.docx",
          "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )],
      },
    });

    const type = await screen.findByLabelText(/document type for schedule\.docx/i);
    await user.click(type);
    await user.click(await screen.findByRole("option", { name: "Schedule" }));
    await user.click(screen.getByRole("button", { name: /upload 1 file/i }));

    expect(await screen.findByText(/DOCX cannot be uploaded as schedule/i)).toBeInTheDocument();
    expect(uploadDocumentMock).not.toHaveBeenCalled();
    expect(getTokenMock).not.toHaveBeenCalled();
  });

  it("uses the provided default document type when a checklist CTA opens upload", async () => {
    render(
      <DocumentUploadDropzone
        projectId="proj_demo_001"
        defaultType="schedule"
      />,
    );

    const dropzone = screen.getByRole("button", { name: /upload documents/i });
    fireEvent.drop(dropzone, {
      dataTransfer: {
        files: [createFile("lookahead.pdf", "application/pdf")],
      },
    });

    expect(await screen.findByText("lookahead.pdf")).toBeInTheDocument();
    expect(screen.getByLabelText(/document type for lookahead\.pdf/i)).toHaveTextContent(
      "Schedule",
    );
  });

  it("uploads staged files sequentially with the selected document type per file", async () => {
    const user = userEvent.setup();
    uploadDocumentMock.mockResolvedValue({ id: "doc-1", task_id: "task-1" });
    getTokenMock.mockResolvedValue("fresh-token-123");

    render(<DocumentUploadDropzone projectId="proj_live_001" />);

    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    await user.upload(input, [
      createFile("contract.pdf", "application/pdf"),
      createFile("schedule.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    ]);

    const scheduleType = await screen.findByLabelText(/document type for schedule\.xlsx/i);
    await user.click(scheduleType);
    await user.click(await screen.findByRole("option", { name: "Schedule" }));
    await user.click(screen.getByRole("button", { name: /upload 2 files/i }));

    await waitFor(() => {
      expect(uploadDocumentMock).toHaveBeenNthCalledWith(
        1,
        "proj_live_001",
        expect.objectContaining({ name: "contract.pdf" }),
        "contract",
        { token: "fresh-token-123" },
      );
      expect(uploadDocumentMock).toHaveBeenNthCalledWith(
        2,
        "proj_live_001",
        expect.objectContaining({ name: "schedule.xlsx" }),
        "schedule",
        { token: "fresh-token-123" },
      );
    });
  });

  it("retries only the unaccepted file after a later upload in the batch fails", async () => {
    const user = userEvent.setup();
    uploadDocumentMock
      .mockResolvedValueOnce({ id: "doc-contract", task_id: "task-contract" })
      .mockRejectedValueOnce(new Error("Upload failed: 500"))
      .mockResolvedValueOnce({ id: "doc-budget", task_id: "task-budget" });
    getTokenMock.mockResolvedValue("fresh-token-123");
    const onUploadComplete = vi.fn();
    const onPartialUploadAccepted = vi.fn();

    render(
      <DocumentUploadDropzone
        projectId="proj_partial"
        onUploadComplete={onUploadComplete}
        onPartialUploadAccepted={onPartialUploadAccepted}
      />,
    );

    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    await user.upload(input, [
      createFile("accepted-contract.pdf", "application/pdf"),
      createFile(
        "retry-budget.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      ),
    ]);
    await user.click(screen.getByRole("button", { name: /upload 2 files/i }));

    expect(await screen.findByText(/1 file\(s\) accepted; 1 remain staged/i)).toBeInTheDocument();
    expect(screen.queryByText("accepted-contract.pdf")).not.toBeInTheDocument();
    expect(screen.getByText("retry-budget.xlsx")).toBeInTheDocument();
    expect(uploadDocumentMock).toHaveBeenCalledTimes(2);
    expect(onPartialUploadAccepted).toHaveBeenCalledTimes(1);
    expect(onUploadComplete).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: /upload 1 file/i }));
    await waitFor(() => expect(uploadDocumentMock).toHaveBeenCalledTimes(3));
    expect(uploadDocumentMock).toHaveBeenNthCalledWith(
      3,
      "proj_partial",
      expect.objectContaining({ name: "retry-budget.xlsx" }),
      "budget",
      { token: "fresh-token-123" },
    );
    expect(await screen.findByText(/upload accepted for 1 file\(s\)/i)).toBeInTheDocument();
    expect(screen.queryByText("retry-budget.xlsx")).not.toBeInTheDocument();
    expect(onUploadComplete).toHaveBeenCalledTimes(1);
    expect(onPartialUploadAccepted).toHaveBeenCalledTimes(1);
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
    fireEvent.click(await screen.findByRole("button", { name: /upload 1 file/i }));

    await waitFor(() => {
      expect(uploadDocumentMock).toHaveBeenCalledWith(
        "proj_live_001",
        expect.objectContaining({ name: "contract.pdf" }),
        "contract",
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
    fireEvent.click(await screen.findByRole("button", { name: /upload 1 file/i }));

    await waitFor(() => {
      expect(uploadDocumentMock).toHaveBeenCalledWith(
        "proj_live_002",
        expect.objectContaining({ name: "contract.pdf" }),
        "contract",
        undefined,
      );
    });
  });

  it("explains server upload failures in plain language", async () => {
    uploadDocumentMock.mockRejectedValue(new Error("Upload failed: 500"));
    getTokenMock.mockResolvedValue("fresh-token-123");

    render(<DocumentUploadDropzone projectId="proj_live_003" />);

    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, {
      target: {
        files: [createFile("contract.pdf", "application/pdf")],
      },
    });
    fireEvent.click(await screen.findByRole("button", { name: /upload 1 file/i }));

    expect(
      await screen.findByText(/upload could not be completed right now/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/the server returned 500 before the file could be queued/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/try again in a moment\. if it keeps happening, contact support\./i),
    ).toBeInTheDocument();
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
