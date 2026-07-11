/**
 * Test Suite ID: TASK-1347
 * Route Coverage: Project alerts page uses generated backend alerts client
 */
import { renderWithProviders, screen, waitFor } from "@/src/tests/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AlertsPage from "./page";

const useProjectAlertsQueryMock = vi.fn();
const alertReviewCenterMock = vi.fn();

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "proj-real-42" }),
}));

vi.mock("@/lib/api/generated/alerts/alerts", () => ({
  useListProjectAlertsApiV1AlertsProjectsProjectIdGet: (...args: unknown[]) =>
    useProjectAlertsQueryMock(...args),
}));

vi.mock("@/hooks/useProjectAlerts", () => ({
  useProjectAlerts: () => ({
    alerts: [],
    loading: false,
    error: null,
  }),
}));

vi.mock("@/components/features/alerts/AlertReviewCenter", () => ({
  AlertReviewCenter: (props: {
    projectId: string;
    alerts: Array<{
      title: string;
      assignee?: string;
      clauseId?: string;
    }>;
  }) => {
    alertReviewCenterMock(props);
    return (
      <div>
        <div>Alert review for {props.projectId}</div>
        {props.alerts.map((alert) => (
          <div key={alert.title}>
            <span>{alert.title}</span>
            <span>{alert.assignee ?? "—"}</span>
            <span>{alert.clauseId ?? "—"}</span>
          </div>
        ))}
      </div>
    );
  },
}));

describe("Project alerts route", () => {
  beforeEach(() => {
    useProjectAlertsQueryMock.mockReset();
    alertReviewCenterMock.mockReset();
  });

  it("loads project alerts through the generated backend query", async () => {
    useProjectAlertsQueryMock.mockReturnValue({
      data: {
        items: [
          {
            id: "alert-1",
            project_id: "proj-real-42",
            tenant_id: "tenant-1",
            rule_code: "TIME-001",
            category: "TIME",
            severity: "critical",
            message: "Schedule drift",
            status: "open",
            created_at: "2026-03-29T00:00:00Z",
          },
        ],
      },
      isLoading: false,
      error: null,
    });

    renderWithProviders(<AlertsPage />);

    await waitFor(() =>
      expect(useProjectAlertsQueryMock).toHaveBeenCalledWith("proj-real-42", undefined),
    );
    const reviewProps = alertReviewCenterMock.mock.calls[0][0];
    expect(reviewProps).toEqual(
      expect.objectContaining({
        projectId: "proj-real-42",
        alerts: [
          expect.objectContaining({
            title: "Schedule drift",
            severity: "critical",
            status: "pending",
          }),
        ],
      }),
    );
    expect(reviewProps.alerts[0]).not.toHaveProperty("assignee");
    expect(reviewProps.alerts[0]).not.toHaveProperty("clauseId");
    expect(screen.getByText(/alert review for proj-real-42/i)).toBeInTheDocument();
    expect(screen.queryByText(/legal\.reviewer|finance\.analyst|project\.manager/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/clause-alert-1/i)).not.toBeInTheDocument();
  });
});
