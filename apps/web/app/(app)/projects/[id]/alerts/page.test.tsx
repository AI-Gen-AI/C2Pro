/**
 * Test Suite ID: TASK-1347
 * Route Coverage: Project alerts page uses generated backend alerts client
 */
import { renderWithProviders, screen, waitFor } from "@/src/tests/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AlertsPage from "./page";

const useProjectAlertsQueryMock = vi.fn();
const alertReviewCenterMock = vi.fn();
const reviewAlertMock = vi.fn();
const resolveAlertMock = vi.fn();
const invalidateQueriesMock = vi.fn();

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "proj-real-42" }),
}));

vi.mock("@/lib/api/generated/alerts/alerts", () => ({
  useListProjectAlertsApiV1AlertsProjectsProjectIdGet: (...args: unknown[]) =>
    useProjectAlertsQueryMock(...args),
  reviewAlertApiV1AlertsAlertIdReviewPost: (...args: unknown[]) =>
    reviewAlertMock(...args),
  resolveAlertApiV1AlertsAlertIdResolvePost: (...args: unknown[]) =>
    resolveAlertMock(...args),
  getListProjectAlertsApiV1AlertsProjectsProjectIdGetQueryKey: (id: string) => [
    "/api/v1/alerts/projects/" + id,
  ],
}));

vi.mock("@/lib/api/generated/coherence-dashboard/coherence-dashboard", () => ({
  getGetCoherenceDashboardApiCoherenceDashboardProjectIdGetQueryKey: (id: string) => [
    "/api/coherence/dashboard/" + id,
  ],
}));

vi.mock("@tanstack/react-query", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@tanstack/react-query")>();
  return {
    ...actual,
    useQueryClient: () => ({ invalidateQueries: invalidateQueriesMock }),
  };
});

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
      status?: string;
    }>;
    onApprove?: (alertId: string) => Promise<void>;
    onReject?: (alertId: string, reason: string) => Promise<void>;
    onResolve?: (alertId: string, resolution: string, rootCause?: string) => Promise<void>;
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
    reviewAlertMock.mockReset();
    resolveAlertMock.mockReset();
    invalidateQueriesMock.mockReset();
    reviewAlertMock.mockResolvedValue({});
    resolveAlertMock.mockResolvedValue({});
    invalidateQueriesMock.mockResolvedValue(undefined);
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

  it("maps canonical persisted alert states after reload", () => {
    useProjectAlertsQueryMock.mockReturnValue({
      data: {
        items: [
          { id: "a1", category: "TIME", severity: "high", message: "A", status: "acknowledged" },
          { id: "a2", category: "LEGAL", severity: "medium", message: "B", status: "dismissed" },
          { id: "a3", category: "SCOPE", severity: "low", message: "C", status: "resolved" },
        ],
      },
      isLoading: false,
      error: null,
    });

    renderWithProviders(<AlertsPage />);
    const reviewProps = alertReviewCenterMock.mock.calls[0][0];
    expect(reviewProps.alerts.map((alert: { status: string }) => alert.status)).toEqual([
      "approved",
      "rejected",
      "approved",
    ]);
  });

  it("persists review and resolution actions then refreshes alerts and coherence", async () => {
    useProjectAlertsQueryMock.mockReturnValue({
      data: {
        items: [
          { id: "a1", category: "TIME", severity: "high", message: "A", status: "open" },
        ],
      },
      isLoading: false,
      error: null,
    });

    renderWithProviders(<AlertsPage />);
    const reviewProps = alertReviewCenterMock.mock.calls[0][0];

    await reviewProps.onApprove("a1");
    expect(reviewAlertMock).toHaveBeenCalledWith("a1", {
      decision: "approve",
      comment: "",
    });

    await reviewProps.onReject("a1", "False positive");
    expect(reviewAlertMock).toHaveBeenCalledWith("a1", {
      decision: "reject",
      comment: "False positive",
    });

    await reviewProps.onResolve("a1", "Underlying issue fixed", "schedule_delay");
    expect(resolveAlertMock).toHaveBeenCalledWith("a1", {
      resolution: "Underlying issue fixed",
      root_cause: "schedule_delay",
    });

    expect(invalidateQueriesMock).toHaveBeenCalledWith({
      queryKey: ["/api/v1/alerts/projects/proj-real-42"],
    });
    expect(invalidateQueriesMock).toHaveBeenCalledWith({
      queryKey: ["/api/coherence/dashboard/proj-real-42"],
    });
  });


});
