/**
 * Test Suite ID: S3-01
 * Backlog Task: TASK-023
 */
import fs from "fs";
import path from "path";
import type { ReactElement } from "react";
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@/src/tests/test-utils";

vi.mock("next/dynamic", () => ({
  default: (
    _loader: unknown,
    options?: {
      loading?: () => ReactElement;
    },
  ) => {
    return function DynamicProxy() {
      return (
        <div data-testid="dynamic-proxy">
          {options?.loading ? options.loading() : null}
        </div>
      );
    };
  },
}));

import { LazyPdfEvidenceViewer } from "./LazyPdfEvidenceViewer";

describe("LazyPdfEvidenceViewer", () => {
  it("[S3-01-PERF-01] exposes a loading fallback while the heavy PDF viewer chunk is resolving", () => {
    render(
      <LazyPdfEvidenceViewer
        fileUrl="/contracts/demo.pdf"
        highlights={[]}
        activeHighlightId={null}
        onHighlightClick={() => undefined}
      />,
    );

    expect(screen.getByTestId("dynamic-proxy")).toBeInTheDocument();
    expect(
      screen.getByTestId("pdf-evidence-viewer-loading"),
    ).toBeInTheDocument();
  });

  it("[S3-01-PERF-02] keeps the evidence surface pointed at the lazy wrapper instead of a direct PDF viewer import", () => {
    const pageSource = fs.readFileSync(
      path.resolve(
        process.cwd(),
        "app",
        "(app)",
        "projects",
        "[id]",
        "evidence",
        "page.tsx",
      ),
      "utf8",
    );
    const viewerPanelSource = fs.readFileSync(
      path.resolve(
        process.cwd(),
        "components",
        "features",
        "evidence",
        "EvidenceViewerPanel.tsx",
      ),
      "utf8",
    );

    expect(viewerPanelSource).toContain("LazyPdfEvidenceViewer");
    expect(pageSource).not.toContain("PdfEvidenceViewer,");
  });
});
