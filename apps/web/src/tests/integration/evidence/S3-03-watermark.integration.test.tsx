/**
 * Test Suite ID: S3-03
 * Roadmap Reference: S3-03 Dynamic watermark (pseudonymized ID)
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@/src/tests/test-utils";

async function renderViewer(
  props: React.ComponentProps<
    typeof import("@/components/features/evidence/PdfEvidenceViewer").PdfEvidenceViewer
  >,
) {
  vi.resetModules();
  const { PdfEvidenceViewer } = await import("@/components/features/evidence/PdfEvidenceViewer");
  return render(<PdfEvidenceViewer {...props} />);
}

describe("S3-03 RED - watermark integration", () => {
  beforeEach(() => {
    vi.stubEnv("NEXT_PUBLIC_APP_MODE", "demo");
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    sessionStorage.clear();
  });

  it("[S3-03-RED-INT-01] renders evidence watermark in PDF viewer and persists after interactions", async () => {
    await renderViewer({
      fileUrl: "/contracts/demo.pdf",
      highlights: [
        { id: "h1", clauseId: "c-101", page: 2, text: "Delay penalty", severity: "critical" },
      ],
      activeHighlightId: null,
      onHighlightClick: () => {},
    });

    expect(screen.getByTestId("evidence-watermark-overlay")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /view evidence c-101/i }));
    expect(screen.getByTestId("evidence-watermark-overlay")).toBeInTheDocument();
  });

  it("[S3-03-RED-INT-02] restores pseudonymized watermark identity after remount from session state", async () => {
    sessionStorage.setItem(
      "s3-03-watermark-state",
      JSON.stringify({ pseudonymId: "USR-7AA3C9", environment: "staging" }),
    );

    const { unmount } = await renderViewer({
      fileUrl: "/contracts/demo.pdf",
      highlights: [],
      activeHighlightId: null,
      onHighlightClick: () => {},
    });

    unmount();

    await renderViewer({
      fileUrl: "/contracts/demo.pdf",
      highlights: [],
      activeHighlightId: null,
      onHighlightClick: () => {},
    });

    expect(screen.getByTestId("evidence-watermark-overlay")).toHaveTextContent("USR-7AA3C9");
    expect(screen.getByTestId("evidence-watermark-overlay")).not.toHaveTextContent(/@/);
  });

  it("[S3-03-RED-INT-03] uses non-empty safe fallback watermark when identity payload is missing", async () => {
    await renderViewer({
      fileUrl: "/contracts/demo.pdf",
      highlights: [],
      activeHighlightId: null,
      onHighlightClick: () => {},
    });

    const watermark = screen.getByTestId("evidence-watermark-overlay");
    expect(watermark).toHaveTextContent(/USR-|ANON-/i);
    expect(watermark).not.toHaveTextContent(/@/);
    expect(watermark).not.toHaveTextContent(/\+1\s?\(?\d{3}\)?/i);
  });
});
