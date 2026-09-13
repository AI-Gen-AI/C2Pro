/**
 * Test Suite ID: TS-P0D-REPORT-UI-003
 * Report page: Current state is the default mode; the Audit export stays available.
 * Audit composition coverage (TASK-FRT-188) lives in AuditReportMode.test.tsx.
 */
import { describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { renderWithProviders, screen } from "@/src/tests/test-utils";
import ProjectReportPage from "./page";

vi.mock("next/navigation", () => ({ useParams: () => ({ id: "proj-report-9" }) }));

vi.mock("@/components/features/report/current-state/CurrentStateReportMode", () => ({
  CurrentStateReportMode: ({ projectId }: { projectId: string }) => (
    <div data-testid="current-state-mode">current state for {projectId}</div>
  ),
}));

vi.mock("@/components/features/report/AuditReportMode", () => ({
  AuditReportMode: ({ projectId }: { projectId: string }) => (
    <div data-testid="audit-mode">audit for {projectId}</div>
  ),
}));

describe("ProjectReportPage", () => {
  it("opens on the current state report for the project", () => {
    renderWithProviders(<ProjectReportPage />);
    expect(screen.getByRole("tab", { name: "Current state" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByTestId("current-state-mode")).toHaveTextContent("current state for proj-report-9");
    expect(screen.queryByTestId("audit-mode")).toBeNull();
  });

  it("keeps the audit export reachable as a second mode", async () => {
    const user = userEvent.setup();
    renderWithProviders(<ProjectReportPage />);
    await user.click(screen.getByRole("tab", { name: "Audit export" }));
    expect(screen.getByTestId("audit-mode")).toHaveTextContent("audit for proj-report-9");
    expect(screen.queryByTestId("current-state-mode")).toBeNull();
  });
});
