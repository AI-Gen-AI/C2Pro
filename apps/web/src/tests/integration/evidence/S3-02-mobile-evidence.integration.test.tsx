/**
 * Test Suite ID: S3-02
 * Roadmap Reference: S3-02 Mobile Evidence Viewer (tab interface)
 */
import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@/src/tests/test-utils";
import { MobileEvidenceViewer } from "@/src/components/features/evidence/MobileEvidenceViewer";

describe("S3-02 RED - mobile evidence integration", () => {
  it("[S3-02-RED-INT-01] keeps desktop split-view off under mobile tab contract", () => {
    render(
      <MobileEvidenceViewer
        pdfState={{ page: 1, zoom: 1 }}
        highlights={[{ id: "h1", clauseId: "c-1", text: "Clause", page: 1 }]}
        alerts={[{ id: "a1", clauseId: "c-1", title: "Alert 1" }]}
        onSelectAlert={() => {}}
      />,
    );

    expect(screen.queryByTestId("desktop-split-view")).not.toBeInTheDocument();
    expect(screen.getByRole("tablist")).toBeInTheDocument();
  });

  it("[S3-02-RED-INT-02] alert selection in alerts tab activates matching PDF highlight", () => {
    render(
      <MobileEvidenceViewer
        pdfState={{ page: 2, zoom: 1 }}
        highlights={[
          { id: "h2", clauseId: "c-2", text: "Compensation", page: 2 },
        ]}
        alerts={[{ id: "a2", clauseId: "c-2", title: "Compensation risk" }]}
        onSelectAlert={() => {}}
      />,
    );

    fireEvent.click(screen.getByRole("tab", { name: /alerts/i }));
    fireEvent.click(screen.getByRole("button", { name: /compensation risk/i }));
    fireEvent.click(screen.getByRole("tab", { name: /pdf/i }));

    expect(screen.getByTestId("mobile-active-highlight")).toHaveTextContent(
      /c-2/i,
    );
  });

  it("[S3-02-ADD-RED-03] preserves active tab/anchor across mobile viewport width changes", () => {
    render(
      <MobileEvidenceViewer
        pdfState={{ page: 4, zoom: 1.1 }}
        highlights={[{ id: "h4", clauseId: "c-4", text: "Insurance", page: 4 }]}
        alerts={[{ id: "a4", clauseId: "c-4", title: "Insurance gap" }]}
        onSelectAlert={() => {}}
      />,
    );

    fireEvent.click(screen.getByRole("tab", { name: /alerts/i }));
    fireEvent.click(screen.getByRole("button", { name: /insurance gap/i }));

    // Contract expects explicit viewport-resize handler signal.
    fireEvent(window, new Event("resize"));
    expect(screen.getByTestId("mobile-viewport-state")).toHaveTextContent(
      /width: 430/i,
    );

    fireEvent.click(screen.getByRole("tab", { name: /pdf/i }));
    expect(screen.getByTestId("mobile-active-highlight")).toHaveTextContent(/c-4/i);
  });

  it("[S3-02-ADD-RED-04] restores active tab and clause from persisted session after remount", () => {
    sessionStorage.setItem(
      "s3-02-mobile-evidence-state",
      JSON.stringify({ tab: "alerts", clauseId: "c-77" }),
    );

    render(
      <MobileEvidenceViewer
        pdfState={{ page: 7, zoom: 1 }}
        highlights={[{ id: "h77", clauseId: "c-77", text: "Retention", page: 7 }]}
        alerts={[{ id: "a77", clauseId: "c-77", title: "Retention risk" }]}
        onSelectAlert={() => {}}
      />,
    );

    expect(screen.getByRole("tab", { name: /alerts/i })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    fireEvent.click(screen.getByRole("tab", { name: /pdf/i }));
    expect(screen.getByTestId("mobile-active-highlight")).toHaveTextContent(/c-77/i);
  });

  it("[S3-02-ADD-RED-07] supports offscreen alert selection continuity in virtualized list", () => {
    const alerts = Array.from({ length: 600 }).map((_, i) => ({
      id: `a-${i + 1}`,
      clauseId: `c-${i + 1}`,
      title: `Alert ${i + 1}`,
    }));

    render(
      <MobileEvidenceViewer
        pdfState={{ page: 10, zoom: 1 }}
        highlights={[{ id: "h-550", clauseId: "c-550", text: "Late delivery", page: 10 }]}
        alerts={alerts}
        onSelectAlert={() => {}}
      />,
    );

    fireEvent.click(screen.getByRole("tab", { name: /alerts/i }));
    fireEvent.click(screen.getByRole("button", { name: /alert 550/i }));
    fireEvent.click(screen.getByRole("tab", { name: /pdf/i }));

    expect(screen.getByTestId("mobile-active-highlight")).toHaveTextContent(/c-550/i);
  });
});
