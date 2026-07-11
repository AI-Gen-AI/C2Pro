/**
 * Test Suite ID: TASK-FRT-188
 * Route Coverage: project audit report export route.
 */
import { describe, expect, it, vi, beforeEach } from "vitest";
import { renderWithProviders, screen, waitFor } from "@/src/tests/test-utils";
import ProjectReportPage from "./page";

const useParamsMock = vi.fn();
const useProjectMock = vi.fn();
const getDashboardSummaryMock = vi.fn();
const useProjectAlertsMock = vi.fn();
const useProjectDocumentsMock = vi.fn();

vi.mock("next/navigation", () => ({
  useParams: () => useParamsMock(),
}));

vi.mock("@/hooks/useProject", () => ({
  useProject: (...args: unknown[]) => useProjectMock(...args),
}));

vi.mock("@/hooks/useProjectDocuments", () => ({
  useProjectDocuments: (...args: unknown[]) => useProjectDocumentsMock(...args),
}));

vi.mock("@/lib/api/services/dashboard", () => ({
  getDashboardSummary: (...args: unknown[]) => getDashboardSummaryMock(...args),
}));

vi.mock("@/lib/api/generated/alerts/alerts", () => ({
  useListProjectAlertsApiV1AlertsProjectsProjectIdGet: (...args: unknown[]) =>
    useProjectAlertsMock(...args),
}));

describe("ProjectReportPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useParamsMock.mockReturnValue({ id: "proj-188" });
    useProjectMock.mockReturnValue({
      data: {
        id: "proj-188",
        name: "Hospital North",
        code: "HN-01",
        status: "active",
        created_at: "2026-07-01T00:00:00Z",
        updated_at: "2026-07-10T00:00:00Z",
      },
      isLoading: false,
      error: null,
    });
    getDashboardSummaryMock.mockResolvedValue({
      project_id: "proj-188",
      tenant_id: "tenant-188",
      coherence_score: 88,
      global_score: 88,
      sub_scores: {},
      weights_used: {},
      alert_count: 1,
      document_count: 1,
      methodology_version: "v2",
      score_version: "coherence-v2",
      score_reason: null,
      score_missing_dimensions: [],
      last_updated: "2026-07-10T10:00:00Z",
    });
    useProjectAlertsMock.mockReturnValue({
      data: {
        items: [
          {
            id: "alert-1",
            project_id: "proj-188",
            tenant_id: "tenant-188",
            rule_code: "DET-BUD-SUM",
            category: "BUDGET",
            severity: "high",
            message: "Budget mismatch requires review.",
            status: "open",
            created_at: "2026-07-10T09:00:00Z",
          },
        ],
        total: 1,
      },
      isLoading: false,
      error: null,
    });
    useProjectDocumentsMock.mockReturnValue({
      documents: [
        {
          id: "doc-budget",
          name: "Budget.xlsx",
          type: "budget",
          extension: "xlsx",
          url: "",
          status: "parsed",
        },
      ],
      loading: false,
      error: null,
      refetch: vi.fn(),
    });
  });

  it("composes the audit report from project, dashboard, alerts, and document sources", async () => {
    renderWithProviders(<ProjectReportPage />);

    await waitFor(() => {
      expect(getDashboardSummaryMock).toHaveBeenCalledWith("proj-188");
    });

    expect(useProjectMock).toHaveBeenCalledWith("proj-188");
    expect(useProjectAlertsMock).toHaveBeenCalledWith("proj-188", undefined);
    expect(useProjectDocumentsMock).toHaveBeenCalledWith("proj-188");
    expect(
      await screen.findByRole("heading", { name: /audit report/i }),
    ).toBeInTheDocument();
    expect(screen.getByText("Hospital North")).toBeInTheDocument();
    expect(screen.getByText("Budget mismatch requires review.")).toBeInTheDocument();
  });
});
