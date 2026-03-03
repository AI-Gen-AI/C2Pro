/**
 * Test Suite ID: S3-01
 * Roadmap Reference: S3-01 PDF renderer (lazy) + clause highlighting
 */
import { describe, expect, it } from "vitest";
import { render, screen, fireEvent } from "@/src/tests/test-utils";
import { PdfEvidenceViewer } from "@/components/features/evidence/PdfEvidenceViewer";

describe("S3-01 RED - evidence integration", () => {
  it("[S3-01-RED-INT-01] clicking an alert focuses matching clause highlight", async () => {
    render(
      <PdfEvidenceViewer
        fileUrl="/contracts/demo.pdf"
        highlights={[
          { id: "h1", clauseId: "c-101", page: 2, text: "Delay penalty", severity: "critical" },
        ]}
        activeHighlightId={null}
        onHighlightClick={() => {}}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /view evidence c-101/i }));

    expect(screen.getByTestId("highlight-h1")).toHaveAttribute("data-active", "true");
  });

  it("[S3-01-RED-INT-02] switching documents preserves viewer state and rebinds highlights", async () => {
    render(
      <PdfEvidenceViewer
        fileUrl="/contracts/doc-a.pdf"
        highlights={[
          { id: "ha", clauseId: "a-1", page: 1, text: "A", severity: "high" },
        ]}
        activeHighlightId={"ha"}
        onHighlightClick={() => {}}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /document b/i }));

    expect(screen.getByTestId("pdf-page-state")).toHaveTextContent(/page: 1/i);
    expect(screen.getByTestId("highlight-list")).toHaveTextContent(/b-1/i);
  });
});
