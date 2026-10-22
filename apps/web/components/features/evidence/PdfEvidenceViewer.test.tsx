/**
 * Test Suite ID: S3-01
 * Roadmap Reference: S3-01 PDF renderer (lazy) + clause highlighting
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@/src/tests/test-utils";
import type { PdfHighlight } from "@/components/features/evidence/PdfEvidenceViewer";

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
  it("never exposes synthetic document switch or c-101 navigation in production", async () => {
    vi.stubEnv("NEXT_PUBLIC_APP_MODE", "production");
    const PdfEvidenceViewer = await loadPdfEvidenceViewer();
    const onHighlightClick = vi.fn();
    const liveFile = "/api/documents/live-doc/download?revision_id=trusted-rev";
    render(
      <PdfEvidenceViewer
        fileUrl={liveFile}
        highlights={[
          {
            id: "real-source-52",
            clauseId: "5.2",
            page: 3,
            text: "Verified source quotation",
            severity: "high",
          },
        ]}
        activeHighlightId={null}
        onHighlightClick={onHighlightClick}
      />,
    );

    expect(screen.queryByRole("button", { name: "Document B" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "View Evidence c-101" })).not.toBeInTheDocument();
    expect(screen.queryByTestId("highlight-hb")).not.toBeInTheDocument();
    const viewer = await screen.findByTestId("react-pdf-viewer-proxy");
    expect(viewer).toHaveAttribute("data-file", liveFile);
    screen.getByTestId("highlight-real-source-52").click();
    expect(onHighlightClick).toHaveBeenCalledWith("real-source-52");
    await waitFor(() => {
      expect(screen.getByTestId("react-pdf-viewer-proxy")).toHaveAttribute("data-file", liveFile);
      expect(screen.getByTestId("react-pdf-viewer-proxy")).toHaveAttribute("data-page", "3");
      expect(screen.queryByTestId("highlight-hb")).not.toBeInTheDocument();
    });
  });

  it("retains both synthetic walkthrough controls only in explicit demo mode", async () => {
    vi.stubEnv("NEXT_PUBLIC_APP_MODE", "demo");
    const PdfEvidenceViewer = await loadPdfEvidenceViewer();
    const onHighlightClick = vi.fn();
    render(
      <PdfEvidenceViewer
        fileUrl="/contracts/doc-a.pdf"
        highlights={[
          {
            id: "demo-c-101",
            clauseId: "c-101",
            page: 2,
            text: "Demo-only clause",
            severity: "medium",
          },
        ]}
        activeHighlightId={null}
        onHighlightClick={onHighlightClick}
      />,
    );

    const demoEvidence = screen.getByRole("button", { name: "View Evidence c-101" });
    const demoSwitch = screen.getByRole("button", { name: "Document B" });
    await screen.findByTestId("react-pdf-viewer-proxy");
    demoEvidence.click();
    expect(onHighlightClick).toHaveBeenCalledWith("demo-c-101");
    await waitFor(() =>
      expect(screen.getByTestId("react-pdf-viewer-proxy")).toHaveAttribute("data-page", "2"),
    );

    demoSwitch.click();
    await waitFor(() => {
      expect(screen.getByTestId("react-pdf-viewer-proxy")).toHaveAttribute(
        "data-file", "/contracts/doc-b.pdf",
      );
      expect(screen.getByTestId("highlight-hb")).toHaveTextContent("B");
    });
  });

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

  it("refreshes and removes citations when evidence arrives on the same revision URL", async () => {
    const PdfEvidenceViewer = await loadPdfEvidenceViewer();
    const fileUrl = "/api/documents/doc-a/download?revision_id=rev-a";
    const onHighlightClick = vi.fn();
    const { rerender } = render(
      <PdfEvidenceViewer
        fileUrl={fileUrl}
        highlights={[]}
        activeHighlightId={null}
        onHighlightClick={onHighlightClick}
      />,
    );
    await screen.findByTestId("react-pdf-viewer-proxy");
    expect(screen.queryByTestId("highlight-late")).not.toBeInTheDocument();

    rerender(
      <PdfEvidenceViewer
        fileUrl={fileUrl}
        highlights={[
          { id: "late", clauseId: "5.2", page: 4, text: "Delayed verified quote", severity: "high" },
        ]}
        activeHighlightId={null}
        onHighlightClick={onHighlightClick}
      />,
    );
    const late = screen.getByTestId("highlight-late");
    expect(late).toHaveTextContent("Delayed verified quote");
    late.click();
    expect(onHighlightClick).toHaveBeenCalledWith("late");
    await waitFor(() => {
      expect(screen.getByTestId("react-pdf-viewer-proxy")).toHaveAttribute("data-page", "4");
    });

    rerender(
      <PdfEvidenceViewer
        fileUrl={fileUrl}
        highlights={[
          { id: "replacement", clauseId: "6.1", page: 2, text: "Updated source quote", severity: "low" },
        ]}
        activeHighlightId="replacement"
        onHighlightClick={onHighlightClick}
      />,
    );
    expect(screen.queryByTestId("highlight-late")).not.toBeInTheDocument();
    expect(screen.getByTestId("highlight-replacement")).toHaveTextContent("Updated source quote");
    await waitFor(() => {
      expect(screen.getByTestId("react-pdf-viewer-proxy")).toHaveAttribute("data-page", "2");
    });

    rerender(
      <PdfEvidenceViewer
        fileUrl={fileUrl}
        highlights={[]}
        activeHighlightId={null}
        onHighlightClick={onHighlightClick}
      />,
    );
    expect(screen.queryByTestId("highlight-replacement")).not.toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByTestId("react-pdf-viewer-proxy")).toHaveAttribute("data-page", "1");
    });
  });

  describe("local selection without parent activeHighlightId on the same revision URL", () => {
    const fileUrl = "/api/documents/doc-a/download?revision_id=rev-a";
    const clicked: PdfHighlight = {
      id: "clicked",
      clauseId: "5.2",
      page: 4,
      text: "Clicked verified quote",
      severity: "high",
    };

    async function renderAndClick() {
      const PdfEvidenceViewer = await loadPdfEvidenceViewer();
      const onHighlightClick = vi.fn();
      const view = (highlights: PdfHighlight[]) => (
        <PdfEvidenceViewer
          fileUrl={fileUrl}
          highlights={highlights}
          activeHighlightId={null}
          onHighlightClick={onHighlightClick}
        />
      );
      const { rerender } = render(view([clicked]));
      await screen.findByTestId("react-pdf-viewer-proxy");
      screen.getByTestId("highlight-clicked").click();
      await waitFor(() => {
        expect(screen.getByTestId("react-pdf-viewer-proxy")).toHaveAttribute("data-page", "4");
      });
      expect(screen.getByTestId("highlight-clicked")).toHaveAttribute("data-active", "true");
      expect(onHighlightClick).toHaveBeenCalledWith("clicked");
      return { rerender: (highlights: PdfHighlight[]) => rerender(view(highlights)) };
    }

    it("click then replace: drops the removed citation's selection and page", async () => {
      const { rerender } = await renderAndClick();

      rerender([
        { id: "replacement", clauseId: "6.1", page: 2, text: "Replacement quote", severity: "low" },
      ]);

      expect(screen.queryByTestId("highlight-clicked")).not.toBeInTheDocument();
      expect(screen.getByTestId("highlight-replacement")).toHaveAttribute("data-active", "false");
      await waitFor(() => {
        expect(screen.getByTestId("react-pdf-viewer-proxy")).toHaveAttribute("data-page", "1");
      });
      expect(screen.getByTestId("pdf-page-state")).toHaveTextContent("Page: 1");
    });

    it("click then clear: resets to page 1 and never resurrects the stale selection", async () => {
      const { rerender } = await renderAndClick();

      rerender([]);

      expect(screen.queryByTestId("highlight-clicked")).not.toBeInTheDocument();
      await waitFor(() => {
        expect(screen.getByTestId("react-pdf-viewer-proxy")).toHaveAttribute("data-page", "1");
      });

      // The same citation id arriving again is new evidence, not the old click.
      rerender([clicked]);
      expect(screen.getByTestId("highlight-clicked")).toHaveAttribute("data-active", "false");
      expect(screen.getByTestId("pdf-page-state")).toHaveTextContent("Page: 1");
    });

    it("replace that retains the clicked citation keeps its selection and page", async () => {
      const { rerender } = await renderAndClick();

      rerender([
        clicked,
        { id: "added", clauseId: "7.4", page: 9, text: "Added quote", severity: "medium" },
      ]);

      expect(screen.getByTestId("highlight-clicked")).toHaveAttribute("data-active", "true");
      expect(screen.getByTestId("highlight-added")).toHaveAttribute("data-active", "false");
      expect(screen.getByTestId("react-pdf-viewer-proxy")).toHaveAttribute("data-page", "4");
    });
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
      // Lazy PDFViewer may remount on revision B; query the CURRENT DOM node,
      // not the stale ref obtained before the A-to-B transition.
      expect(screen.getByTestId("react-pdf-viewer-proxy")).toHaveAttribute(
        "data-file", "/api/documents/doc-a/download?revision_id=rev-b"
      );
      expect(screen.getByTestId("react-pdf-viewer-proxy")).toHaveAttribute("data-page", "5");
    });
  });

  it("clears a previously cited page when the same revision falls back to the document", async () => {
    const PdfEvidenceViewer = await loadPdfEvidenceViewer();
    const highlights = [
      { id: "verified-clause", clauseId: "5.2", page: 3, text: "source", severity: "high" as const },
    ];
    const { rerender } = render(
      <PdfEvidenceViewer
        fileUrl="/api/documents/doc-a/download?revision_id=rev-a"
        highlights={highlights}
        activeHighlightId="verified-clause"
        onHighlightClick={() => {}}
      />,
    );
    await screen.findByTestId("react-pdf-viewer-proxy");
    await waitFor(() =>
      expect(screen.getByTestId("react-pdf-viewer-proxy")).toHaveAttribute("data-page", "3"),
    );

    rerender(
      <PdfEvidenceViewer
        fileUrl="/api/documents/doc-a/download?revision_id=rev-a"
        highlights={highlights}
        activeHighlightId={null}
        onHighlightClick={() => {}}
      />,
    );
    await waitFor(() => {
      expect(screen.getByTestId("react-pdf-viewer-proxy")).toHaveAttribute("data-page", "1");
      expect(screen.getByTestId("react-pdf-viewer-proxy")).toHaveAttribute("data-active-highlight", "none");
    });

    rerender(
      <PdfEvidenceViewer
        fileUrl="/api/documents/doc-a/download?revision_id=rev-a"
        highlights={highlights}
        activeHighlightId="unknown-clause"
        onHighlightClick={() => {}}
      />,
    );
    await waitFor(() =>
      expect(screen.getByTestId("react-pdf-viewer-proxy")).toHaveAttribute("data-page", "1"),
    );
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
