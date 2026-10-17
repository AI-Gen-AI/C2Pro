/**
 * Test Suite ID: S3-01
 * Roadmap Reference: S3-01 PDF renderer (lazy) + clause highlighting
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@/src/tests/test-utils";

vi.mock("@/components/evidence/pdf/PDFViewer", () => ({
  PDFViewer: ({
    file,
    initialPage,
    activeHighlightId,
  }: {
    file: string;
    initialPage?: number;
    activeHighlightId?: string | null;
  }) => (
    <div
      data-testid="react-pdf-viewer-proxy"
      data-file={file}
      data-page={String(initialPage ?? 1)}
      data-active-highlight={activeHighlightId ?? "none"}
    />
  ),
}));

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

    const viewer = await screen.findByTestId("react-pdf-viewer-proxy");
    expect(viewer).toHaveAttribute("data-file", "/api/documents/doc-1/download");
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

  it("[S3-01-RED-UNIT-06] delegates document rendering to the shared react-pdf viewer", async () => {
    const PdfEvidenceViewer = await loadPdfEvidenceViewer();

    render(
      <PdfEvidenceViewer
        fileUrl="/api/documents/doc-2/download"
        highlights={[]}
        activeHighlightId={"active-h-1"}
        onHighlightClick={() => {}}
      />,
    );

    const viewerProxy = await screen.findByTestId("react-pdf-viewer-proxy");
    expect(viewerProxy).toHaveAttribute(
      "data-file",
      "/api/documents/doc-2/download",
    );
    expect(viewerProxy).toHaveAttribute("data-active-highlight", "none");
    expect(screen.queryByTitle(/pdf document viewer/i)).not.toBeInTheDocument();
  });

  it("opens a revision-bound clause on its verified PDF page, not page 1", async () => {
    const PdfEvidenceViewer = await loadPdfEvidenceViewer();
    render(
      <PdfEvidenceViewer
        fileUrl="/api/documents/doc-a/download?revision_id=rev-a"
        highlights={[
          {
            id: "source-clause-52",
            clauseId: "52",
            page: 3,
            text: "Verified source clause 5.2",
            severity: "high",
          },
        ]}
        activeHighlightId="source-clause-52"
        onHighlightClick={() => {}}
      />,
    );

    const viewer = await screen.findByTestId("react-pdf-viewer-proxy");
    await waitFor(() => {
      expect(viewer).toHaveAttribute("data-page", "3");
    });
    expect(viewer).toHaveAttribute(
      "data-file",
      "/api/documents/doc-a/download?revision_id=rev-a",
    );
  });

  it("navigates on a new source highlight and revision switch without stale pages", async () => {
    const PdfEvidenceViewer = await loadPdfEvidenceViewer();
    const sourceA = [
      { id: "source-a", clauseId: "a", page: 4, text: "A", severity: "high" as const },
      { id: "source-a2", clauseId: "a2", page: 2, text: "A2", severity: "low" as const },
    ];
    const { rerender } = render(
      <PdfEvidenceViewer
        fileUrl="/api/documents/doc-a/download?revision_id=rev-a"
        highlights={sourceA}
        activeHighlightId="source-a"
        onHighlightClick={() => {}}
      />,
    );
    const viewer = await screen.findByTestId("react-pdf-viewer-proxy");
    await waitFor(() => expect(viewer).toHaveAttribute("data-page", "4"));

    rerender(
      <PdfEvidenceViewer
        fileUrl="/api/documents/doc-a/download?revision_id=rev-a"
        highlights={sourceA}
        activeHighlightId="source-a2"
        onHighlightClick={() => {}}
      />,
    );
    await waitFor(() => expect(viewer).toHaveAttribute("data-page", "2"));

    rerender(
      <PdfEvidenceViewer
        fileUrl="/api/documents/doc-a/download?revision_id=rev-b"
        highlights={[
          { id: "source-b", clauseId: "b", page: 5, text: "B", severity: "high" },
        ]}
        activeHighlightId="source-b"
        onHighlightClick={() => {}}
      />,
    );
    await waitFor(() => {
      expect(viewer).toHaveAttribute("data-file", "/api/documents/doc-a/download?revision_id=rev-b");
      expect(viewer).toHaveAttribute("data-page", "5");
    });
  });

  it("never guesses a PDF page for unknown or document-fallback source links", async () => {
    const PdfEvidenceViewer = await loadPdfEvidenceViewer();
    const { rerender } = render(
      <PdfEvidenceViewer
        fileUrl="/api/documents/doc-a/download?revision_id=rev-a"
        highlights={[]}
        activeHighlightId={null}
        onHighlightClick={() => {}}
      />,
    );
    const viewer = await screen.findByTestId("react-pdf-viewer-proxy");
    expect(viewer).toHaveAttribute("data-page", "1");

    rerender(
      <PdfEvidenceViewer
        fileUrl="/api/documents/doc-a/download?revision_id=rev-a"
        highlights={[]}
        activeHighlightId="unverified-clause"
        onHighlightClick={() => {}}
      />,
    );
    await waitFor(() => expect(viewer).toHaveAttribute("data-page", "1"));
  });

});
