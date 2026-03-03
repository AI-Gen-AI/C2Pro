/**
 * Test Suite ID: S3-10
 * Roadmap Reference: S3-10 sessionStorage filter persistence
 */
import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@/src/tests/test-utils";
import { FilterPanel } from "@/components/features/filters/FilterPanel";

describe("S3-10 RED - FilterPanel", () => {
  it("[S3-10-RED-UNIT-05] reset clears persisted key and restores defaults", () => {
    sessionStorage.setItem(
      "filters:alerts:proj_demo_001",
      JSON.stringify({
        version: "s3-10-v1",
        filters: { severity: ["critical"], owner: "legal" },
      }),
    );

    render(<FilterPanel routeKey="alerts" projectId="proj_demo_001" />);

    fireEvent.click(screen.getByRole("button", { name: /reset filters/i }));

    expect(screen.getByTestId("filter-state")).toHaveTextContent(/severity:\s*none/i);
    expect(sessionStorage.getItem("filters:alerts:proj_demo_001")).toBeNull();
  });
});
