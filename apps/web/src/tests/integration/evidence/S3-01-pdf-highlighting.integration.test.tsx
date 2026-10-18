/**
 * Test Suite ID: S3-01
 * Roadmap Reference: S3-01 PDF renderer (lazy) + clause highlighting
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, fireEvent } from "@/src/tests/test-utils";

async function loadDemoPdfEvidenceViewer() {
  // APP_MODE is evaluated when config/env is imported. Load the component
  // only after setting demo mode to keep this integration test intentionally
  // separate from the authenticated production viewer.
  vi.stubEnv("NEXT_PUBLIC_APP_MODE", "demo");
  return (await import("@/components/features/evidence/PdfEvidenceViewer")).PdfEvidenceViewer;
}

afterEach(() => {
  cleanup();
  vi.unstubAllEnvs();
  vi.resetModules();
});

vi.mock("@/components/evidence/pdf/PDFViewer", () => ({
  PDFViewer: () => <div data-testid="react-pdf-viewer-proxy" />,
}));

describe("S3-01 RED - evidence integration", () => {
  it("[S3-01-RED-INT-01] clicking an alert focuses matching clause highlight", async () => {
    const PdfEvidenceViewer = await loadDemoPdfEvidenceViewer();
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
    const PdfEvidenceViewer = await loadDemoPdfEvidenceViewer();
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
