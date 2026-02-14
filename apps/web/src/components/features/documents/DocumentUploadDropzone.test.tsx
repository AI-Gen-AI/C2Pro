/**
 * Test Suite ID: S2-09
 * Roadmap Reference: S2-09 Document upload (drag-drop, PDF/XLSX/BC3, chunked)
 */
import { fireEvent, render, screen } from "@/src/tests/test-utils";
import { describe, expect, it } from "vitest";
import { DocumentUploadDropzone } from "@/src/components/features/documents/DocumentUploadDropzone";

function createFile(name: string, type: string, size = 1024): File {
  return new File([new Uint8Array(size)], name, { type });
}

describe("S2-09 RED - DocumentUploadDropzone", () => {
  it("[S2-09-RED-01] accepts only PDF/XLSX/BC3 files", async () => {
    /** Roadmap: S2-09 */
    render(<DocumentUploadDropzone projectId="proj_demo_001" />);

    const dropzone = screen.getByRole("button", { name: /upload documents/i });
    fireEvent.drop(dropzone, {
      dataTransfer: {
        files: [
          createFile("contract.pdf", "application/pdf"),
          createFile(
            "schedule.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
          ),
          createFile("budget.bc3", "application/octet-stream"),
        ],
      },
    });

    expect(
      await screen.findByText(/3 files ready for upload/i),
    ).toBeInTheDocument();
  });

  it("[S2-09-RED-01b] rejects non-allowlisted extensions with explicit error", async () => {
    /** Roadmap: S2-09 */
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
  });

  it("[S2-09-RED-02] updates drag state and aria labels during DnD lifecycle", () => {
    /** Roadmap: S2-09 */
    render(<DocumentUploadDropzone projectId="proj_demo_001" />);

    const dropzone = screen.getByRole("button", { name: /upload documents/i });

    fireEvent.dragEnter(dropzone);
    expect(dropzone).toHaveAttribute("data-drag-state", "active");
    expect(dropzone).toHaveAttribute("aria-label", "Drop files to upload");

    fireEvent.dragLeave(dropzone);
    expect(dropzone).toHaveAttribute("data-drag-state", "idle");
    expect(dropzone).toHaveAttribute("aria-label", "Upload documents");
  });

  it("[S2-09-RED-11] supports keyboard file selection and announces status in live region", async () => {
    /** Roadmap: S2-09 */
    render(<DocumentUploadDropzone projectId="proj_demo_001" />);

    const browseButton = screen.getByRole("button", { name: /browse files/i });
    browseButton.focus();
    fireEvent.keyDown(browseButton, { key: "Enter" });

    expect(screen.getByRole("status")).toHaveTextContent(
      /file picker opened/i,
    );
  });

  it("[S2-09-RED-12] blocks oversize files with exact feedback", async () => {
    /** Roadmap: S2-09 */
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
  });
});

