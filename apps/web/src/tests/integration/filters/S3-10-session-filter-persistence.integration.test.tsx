/**
 * Test Suite ID: S3-10
 * Roadmap Reference: S3-10 sessionStorage filter persistence
 */
import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@/src/tests/test-utils";
import { FilterPersistenceHarness } from "@/components/features/filters/FilterPersistenceHarness";

describe("S3-10 RED - session filter persistence integration", () => {
  it("[S3-10-RED-INT-01] restores filters after remount refresh", () => {
    const { unmount } = render(
      <FilterPersistenceHarness routeKey="alerts" projectId="proj_demo_001" />,
    );

    fireEvent.click(screen.getByRole("button", { name: /severity critical/i }));
    fireEvent.click(screen.getByRole("button", { name: /owner legal/i }));

    unmount();
    render(<FilterPersistenceHarness routeKey="alerts" projectId="proj_demo_001" />);

    expect(screen.getByTestId("filter-state")).toHaveTextContent(/critical/i);
    expect(screen.getByTestId("filter-state")).toHaveTextContent(/legal/i);
  });

  it("[S3-10-RED-INT-02] project namespace isolation keeps filters separate", () => {
    render(<FilterPersistenceHarness routeKey="alerts" projectId="proj_demo_001" />);
    fireEvent.click(screen.getByRole("button", { name: /severity high/i }));

    const { unmount } = render(
      <FilterPersistenceHarness routeKey="alerts" projectId="proj_demo_002" />,
    );

    expect(screen.getAllByTestId("filter-state")[1]).toHaveTextContent(/severity:\s*none/i);
    unmount();
  });

  it("[S3-10-RED-INT-03] malformed payload falls back to defaults with non-blocking warning", () => {
    sessionStorage.setItem("filters:alerts:proj_demo_001", "{broken");

    render(<FilterPersistenceHarness routeKey="alerts" projectId="proj_demo_001" />);

    expect(screen.getByTestId("filter-state")).toHaveTextContent(/severity:\s*none/i);
    expect(screen.getByRole("status")).toHaveTextContent(/restored defaults/i);
  });

  it("[S3-10-RED-INT-04] hydrated filters trigger immediate refetch contract", () => {
    sessionStorage.setItem(
      "filters:alerts:proj_demo_001",
      JSON.stringify({
        version: "s3-10-v1",
        filters: { severity: ["critical"], owner: "legal" },
      }),
    );

    render(<FilterPersistenceHarness routeKey="alerts" projectId="proj_demo_001" />);

    expect(screen.getByTestId("refetch-state")).toHaveTextContent(/refetch:critical\|legal/i);
  });
});
