/**
 * Test Suite ID: TS-UD-COH-V1-09
 * Coverage: Coherence v1 score-version UX and audit-incomplete banner
 */
import { render, screen } from "@/src/tests/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";

import { CoherenceClient } from "./CoherenceClient";

const listProjectAlertsMock = vi.fn();

vi.mock("@/components/coherence/CoherenceGauge", () => ({
  CoherenceGauge: ({ score }: { score: number }) => <div>Gauge {score}</div>,
}));

vi.mock("@/components/coherence/BreakdownChart", () => ({
  BreakdownChart: () => <div>Breakdown chart</div>,
}));

vi.mock("@/components/coherence/RadarView", () => ({
  RadarView: () => <div>Radar chart</div>,
}));

vi.mock("@/components/coherence/AlertsDistribution", () => ({
  AlertsDistribution: ({
    critical,
    high,
    medium,
    low,
  }: {
    critical: number;
    high: number;
    medium: number;
    low: number;
  }) => (
    <div>
      Alerts chart critical:{critical} high:{high} medium:{medium} low:{low}
    </div>
  ),
}));

vi.mock("@/components/coherence/CategoryDetail", () => ({
  CategoryDetail: () => <div>Category detail</div>,
}));

vi.mock("@/components/coherence/ScoreCard", () => ({
  ScoreCard: ({
    category,
    score,
    alertCount,
    onClick,
  }: {
    category: string;
    score: number;
    alertCount: number;
    onClick?: () => void;
  }) => (
    <button type="button" onClick={onClick}>
      {category} {score} alerts:{alertCount}
    </button>
  ),
}));

vi.mock("@/lib/api/generated/alerts/alerts", () => ({
  useListProjectAlertsApiV1ProjectsProjectIdAlertsGet: (...args: unknown[]) =>
    listProjectAlertsMock(...args),
}));

describe("CoherenceClient v1 UX", () => {
  beforeEach(() => {
    listProjectAlertsMock.mockReset();
    listProjectAlertsMock.mockReturnValue({
      data: { items: [] },
      isLoading: false,
      error: null,
    });
  });

  it("renders no internal v1 announcement banner for scored audits", () => {
    render(
      <CoherenceClient
        summary={{
          project_id: "proj-1",
          tenant_id: "tenant-1",
          coherence_score: 82,
          global_score: 82,
          sub_scores: { BUDGET: 80 },
          weights_used: { BUDGET: 1 },
          alert_count: 2,
          document_count: 3,
          methodology_version: "v1",
          score_version: "coherence-v1",
          score_reason: null,
          score_missing_dimensions: [],
          last_updated: "2026-05-01T00:00:00Z",
        }}
      />,
    );

    expect(screen.queryByText(/coherence score v1 is active/i)).not.toBeInTheDocument();
    expect(screen.getByText("(v1)")).toBeInTheDocument();
    expect(screen.getByText(/gauge 82/i)).toBeInTheDocument();
  });

  it("uses real alert severities and categories for distribution and category counts", async () => {
    const user = userEvent.setup();
    listProjectAlertsMock.mockReturnValue({
      data: {
        items: [
          { id: "a1", severity: "critical", category: "BUDGET", status: "open", message: "Budget risk" },
          { id: "a2", severity: "high", category: "BUDGET", status: "open", message: "Budget drift" },
          { id: "a3", severity: "medium", category: "TIME", status: "open", message: "Schedule drift" },
          { id: "a4", severity: "low", category: "LEGAL", status: "open", message: "Legal wording" },
        ],
      },
      isLoading: false,
      error: null,
    });

    render(
      <CoherenceClient
        summary={{
          project_id: "proj-1",
          tenant_id: "tenant-1",
          coherence_score: 82,
          global_score: 82,
          sub_scores: { BUDGET: 80, TIME: 70 },
          weights_used: { BUDGET: 0.5, TIME: 0.5 },
          alert_count: 4,
          document_count: 3,
          methodology_version: "v1",
          score_version: "coherence-v1",
          score_reason: null,
          score_missing_dimensions: [],
          last_updated: "2026-05-01T00:00:00Z",
        }}
      />,
    );

    expect(listProjectAlertsMock).toHaveBeenCalledWith("proj-1", undefined);
    await user.click(screen.getAllByRole("button", { name: /^alerts$/i })[0]);

    expect(screen.getByText(/alerts chart critical:1 high:1 medium:1 low:1/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /budget 80 alerts:2/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /time 70 alerts:1/i })).toBeInTheDocument();
  });

  it("renders an honest alert-data placeholder when alerts are unavailable", async () => {
    const user = userEvent.setup();
    listProjectAlertsMock.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error("alerts unavailable"),
    });

    render(
      <CoherenceClient
        summary={{
          project_id: "proj-1",
          tenant_id: "tenant-1",
          coherence_score: 82,
          global_score: 82,
          sub_scores: { BUDGET: 80 },
          weights_used: { BUDGET: 1 },
          alert_count: 4,
          document_count: 3,
          methodology_version: "v1",
          score_version: "coherence-v1",
          score_reason: null,
          score_missing_dimensions: [],
          last_updated: "2026-05-01T00:00:00Z",
        }}
      />,
    );

    await user.click(screen.getAllByRole("button", { name: /^alerts$/i })[0]);

    expect(screen.getByText(/no alert data/i)).toBeInTheDocument();
    expect(screen.queryByText(/alerts chart/i)).not.toBeInTheDocument();
  });
});

describe("CoherenceClient v1 incomplete score UX", () => {
  beforeEach(() => {
    listProjectAlertsMock.mockReset();
    listProjectAlertsMock.mockReturnValue({
      data: { items: [] },
      isLoading: false,
      error: null,
    });
  });
  it("withholds the gauge and shows an AUDIT_INCOMPLETE banner when score is null", () => {
    render(
      <CoherenceClient
        summary={{
          project_id: "proj-1",
          tenant_id: "tenant-1",
          coherence_score: null,
          global_score: null,
          sub_scores: {},
          weights_used: {},
          alert_count: 1,
          document_count: 1,
          methodology_version: "v1",
          score_version: "coherence-v1",
          score_reason: "insufficient_evidence",
          score_missing_dimensions: ["schedule", "budget"],
          last_updated: "2026-05-01T00:00:00Z",
        }}
      />,
    );

    expect(screen.getByText(/supply missing dimensions to unlock full coherence score/i)).toBeInTheDocument();
    expect(screen.getByText(/schedule, budget/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /upload schedule and budget/i })).toHaveAttribute(
      "href",
      "/projects/proj-1/documents",
    );
    expect(screen.queryByText(/gauge/i)).not.toBeInTheDocument();
  });
});
