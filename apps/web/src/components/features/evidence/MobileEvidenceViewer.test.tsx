/**
 * Test Suite ID: S3-02
 * Roadmap Reference: S3-02 Mobile Evidence Viewer (tab interface)
 */
import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@/src/tests/test-utils";
import { MobileEvidenceViewer } from "@/src/components/features/evidence/MobileEvidenceViewer";

const baseProps = {
  pdfState: { page: 3, zoom: 1.25 },
  highlights: [{ id: "h1", clauseId: "c-101", text: "Delay penalty", page: 2 }],
  alerts: [{ id: "a1", clauseId: "c-101", title: "Delay penalty alert" }],
  onSelectAlert: () => {},
};

describe("S3-02 RED - MobileEvidenceViewer", () => {
  it("[S3-02-RED-UNIT-01] renders PDF and Alerts tabs", () => {
    render(<MobileEvidenceViewer {...baseProps} />);

    expect(screen.getByRole("tab", { name: /pdf/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /alerts/i })).toBeInTheDocument();
  });

  it("[S3-02-RED-UNIT-02] defaults to PDF tab and keeps alerts panel hidden", () => {
    render(<MobileEvidenceViewer {...baseProps} />);

    expect(screen.getByRole("tab", { name: /pdf/i })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByTestId("mobile-panel-pdf")).toBeVisible();
    expect(screen.getByTestId("mobile-panel-alerts")).toHaveAttribute(
      "data-state",
      "inactive",
    );
  });

  it("[S3-02-RED-UNIT-03] updates aria semantics when switching tabs", () => {
    render(<MobileEvidenceViewer {...baseProps} />);

    fireEvent.click(screen.getByRole("tab", { name: /alerts/i }));

    expect(screen.getByRole("tab", { name: /alerts/i })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByRole("tablist")).toBeInTheDocument();
    expect(screen.getByTestId("mobile-panel-alerts")).toHaveAttribute(
      "data-state",
      "active",
    );
  });

  it("[S3-02-RED-UNIT-04] preserves PDF page/zoom state across tab switches", () => {
    render(<MobileEvidenceViewer {...baseProps} />);

    fireEvent.click(screen.getByRole("tab", { name: /alerts/i }));
    fireEvent.click(screen.getByRole("tab", { name: /pdf/i }));

    expect(screen.getByTestId("mobile-pdf-state")).toHaveTextContent(/page: 3/i);
    expect(screen.getByTestId("mobile-pdf-state")).toHaveTextContent(
      /zoom: 1.25/i,
    );
  });

  it("[S3-02-RED-UNIT-05] selecting alert forwards clause anchor to PDF state", () => {
    render(<MobileEvidenceViewer {...baseProps} />);

    fireEvent.click(screen.getByRole("tab", { name: /alerts/i }));
    fireEvent.click(screen.getByRole("button", { name: /delay penalty alert/i }));
    fireEvent.click(screen.getByRole("tab", { name: /pdf/i }));

    expect(screen.getByTestId("mobile-active-highlight")).toHaveTextContent(
      /c-101/i,
    );
  });

  it("[S3-02-RED-UNIT-06] renders explicit empty state when alerts/highlights are empty", () => {
    render(
      <MobileEvidenceViewer
        {...baseProps}
        alerts={[]}
        highlights={[]}
      />,
    );

    expect(screen.getByText(/no alerts available/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: /pdf/i }));
    expect(screen.getByText(/no highlights for this document/i)).toBeInTheDocument();
  });

  it("[S3-02-RED-A11Y-01] supports keyboard tab navigation without focus trap", () => {
    render(<MobileEvidenceViewer {...baseProps} />);

    const pdfTab = screen.getByRole("tab", { name: /pdf/i });
    pdfTab.focus();
    fireEvent.keyDown(pdfTab, { key: "ArrowRight" });

    expect(screen.getByRole("tab", { name: /alerts/i })).toHaveFocus();
  });

  it("[S3-02-ADD-RED-01] does not trap tab focus inside hidden panel", () => {
    render(<MobileEvidenceViewer {...baseProps} />);

    fireEvent.click(screen.getByRole("tab", { name: /alerts/i }));
    const alertsTab = screen.getByRole("tab", { name: /alerts/i });
    alertsTab.focus();
    fireEvent.keyDown(alertsTab, { key: "Tab" });

    // Expects explicit focus handoff element that current implementation does not provide.
    expect(screen.getByTestId("mobile-focus-exit-sentinel")).toHaveFocus();
  });

  it("[S3-02-ADD-RED-02] ignores arrow key tab switching when focus is inside panel content", () => {
    render(<MobileEvidenceViewer {...baseProps} />);

    fireEvent.click(screen.getByRole("tab", { name: /alerts/i }));
    const alertButton = screen.getByRole("button", { name: /delay penalty alert/i });
    alertButton.focus();
    fireEvent.keyDown(alertButton, { key: "ArrowLeft" });

    expect(screen.getByRole("tab", { name: /alerts/i })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByRole("tab", { name: /pdf/i })).toHaveAttribute(
      "aria-selected",
      "false",
    );
  });
});
