/**
 * Test Suite ID: S3-07
 * Roadmap Reference: S3-07 Severity badge + Stakeholder Map + RACI
 */
import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@/src/tests/test-utils";
import { StakeholderRaciWorkbench } from "@/components/features/stakeholders/StakeholderRaciWorkbench";

describe("S3-07 RED - severity/map/raci integration", () => {
  it("[S3-07-RED-INT-01] alert row severity badge links to stakeholder node highlight", () => {
    render(<StakeholderRaciWorkbench />);

    fireEvent.click(screen.getByRole("row", { name: /delay penalty mismatch/i }));

    expect(screen.getByTestId("severity-badge-critical")).toBeInTheDocument();
    expect(screen.getByTestId("stakeholder-node-s1")).toHaveAttribute("data-highlighted", "true");
  });

  it("[S3-07-RED-INT-02] selecting stakeholder node syncs RACI row focus and alert filtering", () => {
    render(<StakeholderRaciWorkbench />);

    fireEvent.click(screen.getByTestId("stakeholder-node-s2"));

    expect(screen.getByTestId("raci-row-w1")).toHaveAttribute("data-focused", "true");
    expect(screen.getByTestId("alerts-filter-state")).toHaveTextContent(/s2/i);
  });

  it("[S3-07-RED-INT-03] RACI edit recomputes map overlays consistently", () => {
    render(<StakeholderRaciWorkbench />);

    fireEvent.click(screen.getByTestId("raci-cell-w1-s2"));
    fireEvent.click(screen.getByRole("button", { name: /set accountable/i }));

    expect(screen.getByTestId("stakeholder-node-s2")).toHaveAttribute("data-raci", "A");
    expect(screen.getByTestId("raci-save-state")).toHaveTextContent(/saved/i);
  });

  it("[S3-07-RED-INT-04] blocks save when multiple Accountable are assigned", () => {
    render(<StakeholderRaciWorkbench />);

    fireEvent.click(screen.getByTestId("raci-cell-w1-s1"));
    fireEvent.click(screen.getByRole("button", { name: /set accountable/i }));
    fireEvent.click(screen.getByTestId("raci-cell-w1-s2"));
    fireEvent.click(screen.getByRole("button", { name: /set accountable/i }));
    fireEvent.click(screen.getByRole("button", { name: /save raci/i }));

    expect(screen.getByRole("alert")).toHaveTextContent(/multiple accountable/i);
  });
});
