/**
 * Test Suite ID: TS-QA-337-ALERTS-PAGE-BRANCH-COV
 * Branch coverage tests for alerts page component
 */
import { renderWithProviders, screen, waitFor } from "@/src/tests/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AlertsPage from "./page";

const useProjectAlertsQueryMock = vi.fn();

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "proj-alerts-42" }),
}));

vi.mock("@/lib/api/generated/alerts/alerts", () => ({
  useListProjectAlertsApiV1AlertsProjectsProjectIdGet: (...args: unknown[]) =>
    useProjectAlertsQueryMock(...args),
}));

vi.mock("@/components/features/alerts/AlertReviewCenter", () => ({
  AlertReviewCenter: (props: {
    projectId: string;
    alerts: Array<{
      id: string;
      title: string;
      severity: string;
      status: string;
    }>;
  }) => (
    <div>
      <div>Alert review for {props.projectId}</div>
      {props.alerts.map((alert) => (
        <div key={alert.id} data-testid={`alert-${alert.id}`}>
          <span>{alert.title}</span>
          <span data-testid={`severity-${alert.id}`}>{alert.severity}</span>
          <span data-testid={`status-${alert.id}`}>{alert.status}</span>
        </div>
      ))}
    </div>
  ),
}));

describe("AlertsPage branch coverage", () => {
  beforeEach(() => {
    useProjectAlertsQueryMock.mockReset();
  });

  it("renders loading state when isLoading is true", () => {
    useProjectAlertsQueryMock.mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
    });

    renderWithProviders(<AlertsPage />);
    expect(screen.getByText(/loading alerts/i)).toBeInTheDocument();
  });

  it("renders error message when error is an Error instance", () => {
    useProjectAlertsQueryMock.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error("Connection refused"),
    });

    renderWithProviders(<AlertsPage />);
    expect(screen.getByText("Connection refused")).toBeInTheDocument();
  });

  it("renders fallback error when error is not an Error instance", () => {
    useProjectAlertsQueryMock.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: "string error",
    });

    renderWithProviders(<AlertsPage />);
    expect(screen.getByText("Failed to load alerts")).toBeInTheDocument();
  });

  it("renders empty state when data.items is undefined", async () => {
    useProjectAlertsQueryMock.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: null,
    });

    renderWithProviders(<AlertsPage />);
    await waitFor(() => {
      expect(screen.getByText(/alert review for proj-alerts-42/i)).toBeInTheDocument();
    });
  });

  it("renders empty state when data.items is empty array", async () => {
    useProjectAlertsQueryMock.mockReturnValue({
      data: { items: [] },
      isLoading: false,
      error: null,
    });

    renderWithProviders(<AlertsPage />);
    await waitFor(() => {
      expect(screen.getByText(/alert review for proj-alerts-42/i)).toBeInTheDocument();
    });
  });

  it("maps all SEVERITY_MAP keys correctly", async () => {
    useProjectAlertsQueryMock.mockReturnValue({
      data: {
        items: [
          {
            id: "a1",
            category: "TIME",
            severity: "critical",
            status: "open",
            message: "Critical alert",
          },
          {
            id: "a2",
            category: "SCOPE",
            severity: "high",
            status: "open",
            message: "High alert",
          },
          {
            id: "a3",
            category: "BUDGET",
            severity: "medium",
            status: "open",
            message: "Medium alert",
          },
          {
            id: "a4",
            category: "LEGAL",
            severity: "low",
            status: "open",
            message: "Low alert",
          },
        ],
      },
      isLoading: false,
      error: null,
    });

    renderWithProviders(<AlertsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("severity-a1")).toHaveTextContent("critical");
      expect(screen.getByTestId("severity-a2")).toHaveTextContent("high");
      expect(screen.getByTestId("severity-a3")).toHaveTextContent("medium");
      expect(screen.getByTestId("severity-a4")).toHaveTextContent("low");
    });
  });

  it("maps all STATUS_MAP keys correctly", async () => {
    useProjectAlertsQueryMock.mockReturnValue({
      data: {
        items: [
          {
            id: "a1",
            category: "TIME",
            severity: "low",
            status: "open",
            message: "Open alert",
          },
          {
            id: "a2",
            category: "SCOPE",
            severity: "low",
            status: "resolved",
            message: "Resolved alert",
          },
          {
            id: "a3",
            category: "BUDGET",
            severity: "low",
            status: "rejected",
            message: "Rejected alert",
          },
        ],
      },
      isLoading: false,
      error: null,
    });

    renderWithProviders(<AlertsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("status-a1")).toHaveTextContent("pending");
      expect(screen.getByTestId("status-a2")).toHaveTextContent("approved");
      expect(screen.getByTestId("status-a3")).toHaveTextContent("rejected");
    });
  });

  it("falls back to medium severity for unmapped severity values", async () => {
    useProjectAlertsQueryMock.mockReturnValue({
      data: {
        items: [
          {
            id: "a-unknown-sev",
            category: "TIME",
            severity: "ultra-critical",
            status: "open",
            message: "Unknown severity",
          },
        ],
      },
      isLoading: false,
      error: null,
    });

    renderWithProviders(<AlertsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("severity-a-unknown-sev")).toHaveTextContent(
        "medium",
      );
    });
  });

  it("falls back to pending status for unmapped status values", async () => {
    useProjectAlertsQueryMock.mockReturnValue({
      data: {
        items: [
          {
            id: "a-unknown-status",
            category: "TIME",
            severity: "low",
            status: "investigating",
            message: "Unknown status",
          },
        ],
      },
      isLoading: false,
      error: null,
    });

    renderWithProviders(<AlertsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("status-a-unknown-status")).toHaveTextContent(
        "pending",
      );
    });
  });

  it("passes correct props to AlertReviewCenter", async () => {
    useProjectAlertsQueryMock.mockReturnValue({
      data: {
        items: [
          {
            id: "a1",
            project_id: "proj-alerts-42",
            tenant_id: "tenant-1",
            rule_code: "TIME-001",
            category: "TIME",
            severity: "high",
            message: "Schedule drift",
            status: "open",
            created_at: "2026-07-01T00:00:00Z",
          },
        ],
      },
      isLoading: false,
      error: null,
    });

    renderWithProviders(<AlertsPage />);
    await waitFor(() => {
      expect(screen.getByText("Schedule drift")).toBeInTheDocument();
      expect(screen.getByText(/alert review for proj-alerts-42/i)).toBeInTheDocument();
    });
  });
});
