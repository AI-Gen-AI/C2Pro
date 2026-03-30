/**
 * Test Suite ID: TASK-1347
 * Route Coverage: Observability real backend integration
 */
import { describe, expect, it, vi } from "vitest";
import { renderWithProviders, screen } from "@/src/tests/test-utils";
import ObservabilityPage from "./page";

const useSystemStatusMock = vi.fn();
const useRecentAnalysesMock = vi.fn();

vi.mock("@/lib/api/generated/observability/observability", () => ({
  useGetSystemStatusApiV1ObservabilityStatusGet: (...args: unknown[]) =>
    useSystemStatusMock(...args),
  useGetRecentAnalysesApiV1ObservabilityAnalysesGet: (...args: unknown[]) =>
    useRecentAnalysesMock(...args),
}));

describe("ObservabilityPage real-data boundary", () => {
  it("renders observability data through generated API hooks", () => {
    useSystemStatusMock.mockReturnValue({
      data: {
        api_status: "OK",
        database_status: "OK",
        timestamp: "2026-03-29T10:00:00Z",
      },
      isLoading: false,
      error: null,
    });
    useRecentAnalysesMock.mockReturnValue({
      data: {
        analyses: [
          {
            id: "analysis-1",
            project_id: "proj-1",
            status: "COMPLETED",
            coherence_score: 88,
            alerts_count: 2,
            started_at: "2026-03-29T09:00:00Z",
            completed_at: "2026-03-29T09:05:00Z",
          },
        ],
        total_analyses: 1,
      },
      isLoading: false,
      error: null,
    });

    renderWithProviders(<ObservabilityPage />);

    expect(screen.getByText(/observability dashboard/i)).toBeInTheDocument();
    expect(screen.getAllByText("OK")).toHaveLength(2);
    expect(screen.getByText(/recent coherence analyses/i)).toBeInTheDocument();
    expect(screen.getByText(/analysis-1/i)).toBeInTheDocument();
    expect(screen.getByText("88")).toBeInTheDocument();
    expect(useSystemStatusMock).toHaveBeenCalled();
    expect(useRecentAnalysesMock).toHaveBeenCalled();
  });
});
