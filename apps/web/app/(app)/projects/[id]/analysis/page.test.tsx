/**
 * Test Suite ID: TASK-1347
 * Route Coverage: Project analysis backend summary
 */
import { describe, expect, it, vi } from "vitest";
import { renderWithProviders, screen } from "@/src/tests/test-utils";
import AnalysisPage from "./page";

const getDashboardMock = vi.fn();
const listProjectAlertsMock = vi.fn();
const getStreamProjectProcessingUrlMock = vi.fn();

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "proj-real-7" }),
}));

vi.mock("@/lib/api/generated/coherence-dashboard/coherence-dashboard", () => ({
  useGetCoherenceDashboardApiCoherenceDashboardProjectIdGet: (...args: unknown[]) =>
    getDashboardMock(...args),
}));

vi.mock("@/lib/api/generated/alerts/alerts", () => ({
  useListProjectAlertsApiV1ProjectsProjectIdAlertsGet: (...args: unknown[]) =>
    listProjectAlertsMock(...args),
}));

vi.mock("@/lib/api/generated/analysis/analysis", () => ({
  getStreamProjectProcessingUrl: (...args: unknown[]) =>
    getStreamProjectProcessingUrlMock(...args),
}));

describe("Project analysis page real-data boundary", () => {
  it("renders backend-backed analysis metrics instead of the placeholder card", () => {
    getDashboardMock.mockReturnValue({
      data: {
        coherence_score: 84,
        sub_scores: { BUDGET: 59 },
        alert_count: 3,
        document_count: 9,
      },
      isLoading: false,
      error: null,
    });
    listProjectAlertsMock.mockReturnValue({
      data: {
        items: [
          {
            id: "alert-1",
            severity: "critical",
            status: "open",
            message: "Date mismatch",
          },
          {
            id: "alert-2",
            severity: "high",
            status: "open",
            message: "Budget drift",
          },
          {
            id: "alert-3",
            severity: "low",
            status: "resolved",
            message: "Closed signal",
          },
        ],
      },
      isLoading: false,
      error: null,
    });
    getStreamProjectProcessingUrlMock.mockReturnValue(
      "/api/v1/analysis/projects/proj-real-7/process/stream",
    );

    renderWithProviders(<AnalysisPage />);

    expect(getDashboardMock).toHaveBeenCalledWith("proj-real-7");
    expect(listProjectAlertsMock).toHaveBeenCalledWith("proj-real-7", undefined);
    expect(screen.getByText(/analysis summary/i)).toBeInTheDocument();
    expect(screen.getAllByText("84").length).toBeGreaterThan(0);
    expect(screen.getAllByText("2").length).toBeGreaterThan(0);
    expect(screen.getAllByText("9").length).toBeGreaterThan(0);
    expect(screen.getByText("41%")).toBeInTheDocument();
    expect(screen.getByText(/date mismatch/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /open processing stream/i })).toHaveAttribute(
      "href",
      "/api/v1/analysis/projects/proj-real-7/process/stream",
    );
    expect(
      screen.queryByText(/centro de alertas, riesgos y hallazgos automatizados/i),
    ).not.toBeInTheDocument();
  });
});
