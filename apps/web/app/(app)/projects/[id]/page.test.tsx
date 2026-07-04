/**
 * Test Suite ID: TASK-1347
 * Route Coverage: Project overview detail page uses generated backend queries
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders, screen } from "@/src/tests/test-utils";

const getDashboardMock = vi.fn();
const listProjectAlertsMock = vi.fn();
const useProjectMock = vi.fn();

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "proj_real_001" }),
}));

vi.mock("@/lib/api/generated/coherence-dashboard/coherence-dashboard", () => ({
  useGetCoherenceDashboardApiCoherenceDashboardProjectIdGet: (...args: unknown[]) =>
    getDashboardMock(...args),
}));

vi.mock("@/lib/api/generated/alerts/alerts", () => ({
  useListProjectAlertsApiV1ProjectsProjectIdAlertsGet: (...args: unknown[]) =>
    listProjectAlertsMock(...args),
}));

vi.mock("@/hooks/useProject", () => ({
  useProject: (...args: unknown[]) => useProjectMock(...args),
}));

import ProjectOverviewPage from "./page";

describe("ProjectOverviewPage", () => {
  beforeEach(() => {
    getDashboardMock.mockReset();
    listProjectAlertsMock.mockReset();
    useProjectMock.mockReset();
    useProjectMock.mockReturnValue({
      data: { status: "active" },
      isLoading: false,
      error: null,
    });
  });

  it("shows a loading state while project summary is being fetched", () => {
    getDashboardMock.mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
    });
    listProjectAlertsMock.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: null,
    });

    renderWithProviders(<ProjectOverviewPage />);

    expect(screen.getByText(/loading project overview/i)).toBeInTheDocument();
  });

  it("surfaces backend errors instead of rendering stale project data", () => {
    getDashboardMock.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error("boom"),
    });
    listProjectAlertsMock.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: null,
    });

    renderWithProviders(<ProjectOverviewPage />);

    expect(screen.getByText(/boom/i)).toBeInTheDocument();
  });

  it("keeps the project overview usable when only the alerts request fails", () => {
    getDashboardMock.mockReturnValue({
      data: {
        coherence_score: 87,
        sub_scores: { BUDGET: 37 },
        alert_count: 5,
        document_count: 12,
      },
      isLoading: false,
      error: null,
    });
    listProjectAlertsMock.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error("alerts unavailable"),
    });

    renderWithProviders(<ProjectOverviewPage />);

    expect(screen.getAllByText("Coherence Score")).toHaveLength(2);
    expect(screen.getByText("Open Alerts")).toBeInTheDocument();
    expect(screen.getByText(/recent alerts unavailable/i)).toBeInTheDocument();
  });

  it("renders coherence, alert, document, and budget summary cards from generated queries", () => {
    getDashboardMock.mockReturnValue({
      data: {
        coherence_score: 87,
        sub_scores: { BUDGET: 37 },
        alert_count: 5,
        document_count: 12,
      },
      isLoading: false,
      error: null,
    });
    listProjectAlertsMock.mockReturnValue({
      data: {
        items: [
          { id: "a1", severity: "critical", status: "open", message: "Delay penalty mismatch", category: "TIME" },
          { id: "a2", severity: "high", status: "open", message: "Missing warranty clause", category: "LEGAL" },
          { id: "a3", severity: "low", status: "resolved", message: "Closed alert", category: "QUALITY" },
        ],
      },
      isLoading: false,
      error: null,
    });

    renderWithProviders(<ProjectOverviewPage />);

    expect(getDashboardMock).toHaveBeenCalledWith("proj_real_001");
    expect(listProjectAlertsMock).toHaveBeenCalledWith("proj_real_001", undefined);
    expect(screen.getAllByText("Coherence Score")).toHaveLength(2);
    expect(screen.getAllByText("87")).toHaveLength(2);
    expect(screen.getByText("Open Alerts")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("Documents")).toBeInTheDocument();
    expect(screen.getByText("12")).toBeInTheDocument();
    expect(screen.getAllByText("Budget coherence")).toHaveLength(2);
    expect(screen.getAllByText("37")).toHaveLength(2);
  });

  it("does not crash when the overview transitions from loading to backend data", () => {
    getDashboardMock.mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
    });
    listProjectAlertsMock.mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
    });

    const { rerender } = renderWithProviders(<ProjectOverviewPage />);

    getDashboardMock.mockReturnValue({
      data: {
        coherence_score: 88,
        sub_scores: { BUDGET: 72 },
        alert_count: 0,
        document_count: 3,
      },
      isLoading: false,
      error: null,
    });
    listProjectAlertsMock.mockReturnValue({
      data: { items: [] },
      isLoading: false,
      error: null,
    });

    expect(() => rerender(<ProjectOverviewPage />)).not.toThrow();
    expect(screen.getAllByText("Budget coherence")).toHaveLength(2);
  });

  it("renders real project status and an honest placeholder when budget coherence is missing", () => {
    useProjectMock.mockReturnValue({
      data: { status: "draft" },
      isLoading: false,
      error: null,
    });
    getDashboardMock.mockReturnValue({
      data: {
        coherence_score: 87,
        sub_scores: { SCOPE: 90 },
        alert_count: 0,
        document_count: 2,
      },
      isLoading: false,
      error: null,
    });
    listProjectAlertsMock.mockReturnValue({
      data: { items: [] },
      isLoading: false,
      error: null,
    });

    renderWithProviders(<ProjectOverviewPage />);

    expect(useProjectMock).toHaveBeenCalledWith("proj_real_001");
    expect(screen.getByText("draft")).toBeInTheDocument();
    expect(screen.queryByText("Active")).not.toBeInTheDocument();
    expect(screen.getAllByText("Budget coherence")).toHaveLength(2);
    expect(screen.getAllByText("—")).toHaveLength(2);
    expect(screen.getAllByTitle("Requires budget document")).toHaveLength(2);
  });

  it("links to the alerts route from the recent alerts panel", () => {
    getDashboardMock.mockReturnValue({
      data: {
        coherence_score: 91,
        sub_scores: { BUDGET: 60 },
        alert_count: 2,
        document_count: 4,
      },
      isLoading: false,
      error: null,
    });
    listProjectAlertsMock.mockReturnValue({
      data: { items: [] },
      isLoading: false,
      error: null,
    });

    renderWithProviders(<ProjectOverviewPage />);

    expect(screen.getByRole("link", { name: /view all/i })).toHaveAttribute(
      "href",
      "/projects/proj_real_001/alerts",
    );
    expect(screen.getByText(/no open alerts/i)).toBeInTheDocument();
  });
});
