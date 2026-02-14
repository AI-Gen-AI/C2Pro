/**
 * Test Suite ID: S3-01
 * Roadmap Reference: S3-01 PDF renderer (lazy) + clause highlighting
 */
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@/src/tests/test-utils";
import { PdfEvidenceViewer } from "@/src/components/features/evidence/PdfEvidenceViewer";

describe("S3-01 RED - PdfEvidenceViewer", () => {
  it("[S3-01-RED-UNIT-01] renders lazy fallback before pdf viewer module resolves", () => {
    vi.mock("react-pdf", () => {
      throw new Error("module not ready");
    });

    render(
      <PdfEvidenceViewer
        fileUrl="/demo.pdf"
        highlights={[]}
        activeHighlightId={null}
        onHighlightClick={() => {}}
      />,
    );

    expect(screen.getByText(/loading pdf viewer/i)).toBeInTheDocument();
  });

  it("[S3-01-RED-UNIT-02] does not eagerly render pdf page container on initial paint", () => {
    render(
      <PdfEvidenceViewer
        fileUrl="/demo.pdf"
        highlights={[]}
        activeHighlightId={null}
        onHighlightClick={() => {}}
      />,
    );

    expect(screen.queryByTestId("pdf-page-canvas")).not.toBeInTheDocument();
  });
});
