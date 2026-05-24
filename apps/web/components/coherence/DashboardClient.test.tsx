/**
 * Test Suite ID: TASK-014
 * Dashboard UI interaction coverage
 */
import type { ReactNode } from "react";
import { fireEvent, render, screen } from "@/src/tests/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DashboardClient } from "./DashboardClient";

vi.mock("@/components/coherence/CoherenceGauge", () => ({
  CoherenceGauge: ({
    score,
    documentsAnalyzed,
  }: {
    score: number;
    documentsAnalyzed: number;
  }) => (
    <div>
      Gauge {score} / {documentsAnalyzed}
    </div>
  ),
}));

vi.mock("@/components/coherence/BreakdownChart", () => ({
  BreakdownChart: ({ data }: { data: Array<{ name: string; score: number }> }) => (
    <div>Breakdown {data.map((entry) => `${entry.name}:${entry.score}`).join(",")}</div>
  ),
}));

vi.mock("@/components/coherence/RadarView", () => ({
  RadarView: ({
    data,
  }: {
    data: Array<{ category: string; score: number; target: number }>;
  }) => <div>Radar {data.map((entry) => `${entry.category}:${entry.score}`).join(",")}</div>,
}));

vi.mock("@/components/coherence/AlertsDistribution", () => ({
  AlertsDistribution: ({ medium }: { medium: number }) => <div>Alerts {medium}</div>,
}));

vi.mock("@/components/coherence/CategoryDetail", () => ({
  CategoryDetail: ({
    category,
    onClose,
  }: {
    category: string;
    onClose: () => void;
  }) => (
    <div>
      <div>Detail {category}</div>
      <button type="button" onClick={onClose}>
        Close Detail
      </button>
    </div>
  ),
}));

vi.mock("@/components/coherence/ScoreCard", () => ({
  ScoreCard: ({
    category,
    score,
    selected,
    onClick,
  }: {
    category: string;
    score: number;
    selected?: boolean;
    onClick?: () => void;
  }) => (
    <button type="button" onClick={onClick}>
      {selected ? "Selected" : "Card"} {category} {score}
    </button>
  ),
}));

vi.mock("next/link", () => ({
  default: ({
    children,
    href,
    ...rest
  }: {
    children: ReactNode;
    href: string;
    [key: string]: unknown;
  }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

const dashboardData = {
  project_id: "proj-1",
  tenant_id: "tenant-1",
  coherence_score: 86,
  global_score: 86,
  sub_scores: {
    BUDGET: 72,
    LEGAL: 91,
    SCOPE: 64,
  },
  weights_used: {
    BUDGET: 0.3,
    LEGAL: 0.4,
    SCOPE: 0.3,
  },
  alert_count: 5,
  document_count: 8,
  methodology_version: "v1",
  last_updated: "2026-03-29T00:00:00Z",
};

afterEach(() => {
  vi.restoreAllMocks();
});

describe("DashboardClient", () => {
  it("renders the breakdown view by default with project context", () => {
    render(<DashboardClient data={dashboardData} projectName="Alpha Project" />);

    expect(screen.getByText(/project \/ alpha project/i)).toBeInTheDocument();
    expect(screen.getByText(/coherence dashboard/i)).toBeInTheDocument();
    expect(screen.getByText(/gauge 86 \/ 8/i)).toBeInTheDocument();
    expect(screen.getByText(/breakdown budget:72,legal:91,scope:64/i)).toBeInTheDocument();
  });

  it("switches to the radar view when selected", () => {
    render(<DashboardClient data={dashboardData} projectName="Alpha Project" />);

    fireEvent.click(screen.getByRole("button", { name: /radar/i }));

    expect(screen.getByText(/radar budget:72,legal:91,scope:64/i)).toBeInTheDocument();
  });

  it("switches to the alerts view and passes the alert count", () => {
    render(<DashboardClient data={dashboardData} projectName="Alpha Project" />);

    fireEvent.click(screen.getByRole("button", { name: /alerts/i }));

    expect(screen.getByText("Alerts 5")).toBeInTheDocument();
  });

  it("supports switching between dashboard layout presets", () => {
    const { container } = render(
      <DashboardClient data={dashboardData} projectName="Alpha Project" />,
    );

    expect(container.querySelector("[data-layout='overview']")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Executive template keeps the overview layout with balanced score distribution.",
      ),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /focus layout/i }));

    expect(container.querySelector("[data-layout='focus']")).toBeInTheDocument();
    expect(screen.getByText("Focus layout emphasizes the selected coherence analysis.")).toBeInTheDocument();
  });

  it("applies dashboard templates that combine layout and view intent", () => {
    const { container } = render(
      <DashboardClient data={dashboardData} projectName="Alpha Project" />,
    );

    fireEvent.click(screen.getByRole("button", { name: /portfolio template/i }));

    expect(container.querySelector("[data-layout='compact']")).toBeInTheDocument();
    expect(screen.getByText("Portfolio template tracks alert load across a denser review surface.")).toBeInTheDocument();
    expect(screen.getByText("Alerts 5")).toBeInTheDocument();
  });

  it("opens and closes category detail panels from score cards", () => {
    render(<DashboardClient data={dashboardData} projectName="Alpha Project" />);

    fireEvent.click(screen.getByRole("button", { name: /card scope 64/i }));
    expect(screen.getByText("Coherence Score Drill-down")).toBeInTheDocument();
    expect(screen.getByText("Detail SCOPE")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /close detail/i }));
    expect(screen.queryByText("Detail SCOPE")).not.toBeInTheDocument();
  });

  it("renders the empty state instead of the gauge when coherence_score is null", () => {
    const nullData = {
      ...dashboardData,
      coherence_score: null,
      global_score: null,
      score_reason: "insufficient_active_weight",
    };
    render(<DashboardClient data={nullData} projectName="Alpha Project" />);

    expect(screen.getByTestId("coherence-empty-state")).toBeInTheDocument();
    expect(screen.getByTestId("empty-state-cta")).toHaveAttribute(
      "href",
      "/projects/proj-1/documents",
    );
    expect(screen.queryByText(/gauge 0 \/ /i)).not.toBeInTheDocument();
  });

  it("never renders a fallback '0' score when coherence_score is null", () => {
    const nullData = {
      ...dashboardData,
      coherence_score: null,
      global_score: null,
    };
    const { container } = render(
      <DashboardClient data={nullData} projectName="Alpha Project" />,
    );
    // The gauge mock would render "Gauge 0 / 8" if the old `?? 0` fallback existed.
    expect(container.textContent).not.toMatch(/Gauge 0 \//);
  });

  it("exports the dashboard summary to PDF and Excel", () => {
    const popupDocument = {
      write: vi.fn(),
      close: vi.fn(),
    };
    const popupWindow = {
      document: popupDocument,
      focus: vi.fn(),
      print: vi.fn(),
    };
    const openSpy = vi.spyOn(window, "open").mockReturnValue(
      popupWindow as unknown as Window,
    );
    const createObjectUrlSpy = vi
      .spyOn(URL, "createObjectURL")
      .mockReturnValue("blob:dashboard-export");
    const revokeObjectUrlSpy = vi
      .spyOn(URL, "revokeObjectURL")
      .mockImplementation(() => undefined);
    const appendSpy = vi.spyOn(document.body, "appendChild");
    const removeSpy = vi.spyOn(document.body, "removeChild");
    const anchorClickSpy = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(() => undefined);

    render(<DashboardClient data={dashboardData} projectName="Alpha Project" />);

    fireEvent.click(screen.getByRole("button", { name: /export pdf/i }));

    expect(openSpy).toHaveBeenCalled();
    expect(popupDocument.write).toHaveBeenCalledWith(
      expect.stringContaining("Alpha Project"),
    );
    expect(popupWindow.print).toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: /export excel/i }));

    expect(createObjectUrlSpy).toHaveBeenCalled();
    expect(anchorClickSpy).toHaveBeenCalled();
    expect(appendSpy).toHaveBeenCalled();
    expect(removeSpy).toHaveBeenCalled();
    expect(revokeObjectUrlSpy).toHaveBeenCalledWith("blob:dashboard-export");
  });
});
