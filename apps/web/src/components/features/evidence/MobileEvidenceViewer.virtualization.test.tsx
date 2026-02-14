/**
 * Test Suite ID: S3-02
 * Roadmap Reference: S3-02 Mobile Evidence Viewer (tab interface)
 */
import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@/src/tests/test-utils";
import { MobileEvidenceViewer } from "@/src/components/features/evidence/MobileEvidenceViewer";

describe("S3-02 RED - MobileEvidenceViewer virtualization", () => {
  it("[S3-02-ADD-RED-05] renders virtual window for 500+ alerts instead of full list", () => {
    const alerts = Array.from({ length: 520 }).map((_, i) => ({
      id: `a-${i + 1}`,
      clauseId: `c-${i + 1}`,
      title: `Alert ${i + 1}`,
    }));

    render(
      <MobileEvidenceViewer
        pdfState={{ page: 1, zoom: 1 }}
        highlights={[]}
        alerts={alerts}
        onSelectAlert={() => {}}
      />,
    );

    fireEvent.click(screen.getByRole("tab", { name: /alerts/i }));

    expect(screen.getByTestId("mobile-alert-virtual-window")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /alert 520/i })).not.toBeInTheDocument();
  });

  it("[S3-02-ADD-RED-06] supports Home/End/PageDown keyboard navigation in virtualized alerts", () => {
    const alerts = Array.from({ length: 520 }).map((_, i) => ({
      id: `a-${i + 1}`,
      clauseId: `c-${i + 1}`,
      title: `Alert ${i + 1}`,
    }));

    render(
      <MobileEvidenceViewer
        pdfState={{ page: 1, zoom: 1 }}
        highlights={[]}
        alerts={alerts}
        onSelectAlert={() => {}}
      />,
    );

    fireEvent.click(screen.getByRole("tab", { name: /alerts/i }));
    const list = screen.getByTestId("mobile-alert-virtual-window");
    list.focus();
    fireEvent.keyDown(list, { key: "End" });

    expect(screen.getByTestId("mobile-alert-active-index")).toHaveTextContent(
      /519/i,
    );
  });
});
