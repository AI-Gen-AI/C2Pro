/**
 * Test Suite ID: S3-07
 * Roadmap Reference: S3-07 Severity badge + Stakeholder Map + RACI
 */
import { describe, expect, it } from "vitest";
import { render, screen } from "@/src/tests/test-utils";
import { RaciGrid } from "@/components/features/stakeholders/RaciGrid";

describe("S3-07 RED - RaciGrid accessibility", () => {
  it("[S3-07-RED-UNIT-06] renders semantic table with keyboard-focusable cells", () => {
    render(
      <RaciGrid
        rows={[{ id: "w1", label: "Permit package" }]}
        columns={[{ id: "s1", label: "Owner" }]}
        values={{ w1: { s1: "A" } }}
      />,
    );

    expect(screen.getByRole("table", { name: /raci grid/i })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: /owner/i })).toBeInTheDocument();
    expect(screen.getByRole("rowheader", { name: /permit package/i })).toBeInTheDocument();
    expect(screen.getByTestId("raci-cell-w1-s1")).toHaveAttribute("tabindex", "0");
  });
});
