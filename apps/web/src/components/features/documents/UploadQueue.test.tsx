/**
 * Test Suite ID: S2-09
 * Roadmap Reference: S2-09 Document upload (drag-drop, PDF/XLSX/BC3, chunked)
 */
import { render, screen } from "@/src/tests/test-utils";
import { describe, expect, it } from "vitest";
import { UploadQueue } from "@/src/components/features/documents/UploadQueue";

describe("S2-09 RED - UploadQueue", () => {
  it("[S2-09-RED-03] preserves deterministic file ordering", () => {
    /** Roadmap: S2-09 */
    render(
      <UploadQueue
        items={[
          { id: "f1", name: "a.pdf", status: "queued", progress: 0 },
          { id: "f2", name: "b.xlsx", status: "queued", progress: 0 },
          { id: "f3", name: "c.bc3", status: "queued", progress: 0 },
        ]}
      />,
    );

    const rows = screen.getAllByTestId(/^upload-row-/);
    expect(rows[0]).toHaveTextContent("a.pdf");
    expect(rows[1]).toHaveTextContent("b.xlsx");
    expect(rows[2]).toHaveTextContent("c.bc3");
  });

  it("[S2-09-RED-03b] renders explicit statuses for queued, uploading, success, and error", () => {
    /** Roadmap: S2-09 */
    render(
      <UploadQueue
        items={[
          { id: "q", name: "queued.pdf", status: "queued", progress: 0 },
          { id: "u", name: "uploading.pdf", status: "uploading", progress: 45 },
          { id: "s", name: "done.pdf", status: "success", progress: 100 },
          { id: "e", name: "bad.pdf", status: "error", progress: 20 },
        ]}
      />,
    );

    expect(screen.getByText(/queued/i)).toBeInTheDocument();
    expect(screen.getByText(/uploading 45%/i)).toBeInTheDocument();
    expect(screen.getByText(/uploaded/i)).toBeInTheDocument();
    expect(screen.getByText(/failed/i)).toBeInTheDocument();
  });
});

