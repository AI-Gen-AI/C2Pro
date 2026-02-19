/**
 * Test Suite ID: S3-07
 * Roadmap Reference: S3-07 Severity badge + Stakeholder Map + RACI
 */
import { describe, expect, it } from "vitest";
import { render, screen } from "@/src/tests/test-utils";
import { SeverityBadge } from "@/components/features/stakeholders/SeverityBadge";

describe("S3-07 RED - SeverityBadge", () => {
  it("[S3-07-RED-UNIT-01] maps severities to deterministic labels and token classes", () => {
    render(
      <>
        <SeverityBadge severity="critical" />
        <SeverityBadge severity="high" />
        <SeverityBadge severity="medium" />
        <SeverityBadge severity="low" />
      </>,
    );

    expect(screen.getByTestId("severity-badge-critical")).toHaveTextContent(/critical/i);
    expect(screen.getByTestId("severity-badge-critical")).toHaveClass("severity-critical");
    expect(screen.getByTestId("severity-badge-high")).toHaveClass("severity-high");
    expect(screen.getByTestId("severity-badge-medium")).toHaveClass("severity-medium");
    expect(screen.getByTestId("severity-badge-low")).toHaveClass("severity-low");
  });

  it("[S3-07-RED-UNIT-02] renders safe fallback for unknown severity", () => {
    render(<SeverityBadge severity={"unknown" as never} />);

    expect(screen.getByTestId("severity-badge-unknown")).toHaveTextContent(/unknown/i);
    expect(screen.getByTestId("severity-badge-unknown")).toHaveClass("severity-unknown");
  });
});
