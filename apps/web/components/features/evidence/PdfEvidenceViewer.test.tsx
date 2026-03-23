/**
 * Test Suite ID: S3-01
 * Roadmap Reference: S3-01 PDF renderer (lazy) + clause highlighting
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@/src/tests/test-utils";

async function loadPdfEvidenceViewer() {
  const module =
    await import("@/components/features/evidence/PdfEvidenceViewer");
  return module.PdfEvidenceViewer;
}

afterEach(() => {
  cleanup();
  window.sessionStorage.clear();
  vi.resetModules();
  vi.unstubAllEnvs();
});

describe("S3-01 RED - PdfEvidenceViewer", () => {
  it("[S3-01-RED-UNIT-01] renders lazy fallback before pdf viewer module resolves", async () => {
    const PdfEvidenceViewer = await loadPdfEvidenceViewer();

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

  it("[S3-01-RED-UNIT-02] does not eagerly render pdf page container on initial paint", async () => {
    const PdfEvidenceViewer = await loadPdfEvidenceViewer();

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

  it("[S3-01-RED-UNIT-03] binds the rendered viewer surface to the provided file URL", async () => {
    const PdfEvidenceViewer = await loadPdfEvidenceViewer();

    render(
      <PdfEvidenceViewer
        fileUrl="/api/documents/doc-1/download"
        highlights={[]}
        activeHighlightId={null}
        onHighlightClick={() => {}}
      />,
    );

    const frame = await screen.findByTestId("pdf-page-canvas");
    expect(frame).toHaveAttribute("src", "/api/documents/doc-1/download");
  });

  it("[S3-01-RED-UNIT-04] ignores demo watermark session state on production viewer paths", async () => {
    vi.stubEnv("NEXT_PUBLIC_APP_MODE", "production");
    window.sessionStorage.setItem(
      "s3-03-watermark-state",
      JSON.stringify({
        pseudonymId: "demo-session-watermark",
        environment: "local",
        timestampIso: "2026-03-21T10:00:00.000Z",
      }),
    );
    const PdfEvidenceViewer = await loadPdfEvidenceViewer();

    render(
      <PdfEvidenceViewer
        fileUrl="/api/documents/doc-1/download"
        highlights={[]}
        activeHighlightId={null}
        onHighlightClick={() => {}}
      />,
    );

    const watermark = screen.getAllByTestId("evidence-watermark-tile")[0];
    expect(watermark).not.toHaveTextContent("demo-session-watermark");
    expect(watermark).not.toHaveTextContent("local");
  });

  it("[S3-01-RED-UNIT-05] avoids synthesizing unverified production watermark payloads", async () => {
    vi.stubEnv("NEXT_PUBLIC_APP_MODE", "production");
    const PdfEvidenceViewer = await loadPdfEvidenceViewer();

    render(
      <PdfEvidenceViewer
        fileUrl="/api/documents/doc-1/download"
        highlights={[]}
        activeHighlightId={null}
        onHighlightClick={() => {}}
      />,
    );

    const watermark = screen.getAllByTestId("evidence-watermark-tile")[0];
    expect(watermark).not.toHaveTextContent("unverified-production-access");
    await waitFor(() => {
      expect(window.sessionStorage.getItem("s3-03-watermark-state")).toBeNull();
    });
  });
});
