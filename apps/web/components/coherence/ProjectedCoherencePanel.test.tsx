/**
 * #714 trusted vs projected Coherence: the trusted score is canonical and
 * solid; the projected score is visibly provisional and never replaces it.
 */
import { render, screen } from "@/src/tests/test-utils";
import { describe, expect, it } from "vitest";

import type { DashboardSummary } from "@/lib/api/contracts";
import { ProjectedCoherencePanel } from "./ProjectedCoherencePanel";

function summary(overrides: Partial<DashboardSummary> = {}): DashboardSummary {
  return {
    project_id: "proj-1",
    tenant_id: "tenant-1",
    coherence_score: 80,
    global_score: 80,
    trusted_score: 80,
    sub_scores: {},
    weights_used: {},
    alert_count: 0,
    document_count: 2,
    methodology_version: "3.0",
    score_version: "coherence-v1",
    last_updated: "2026-09-27T12:00:00Z",
    projected_score: 60,
    projected_delta: -20,
    pending_review_count: 2,
    projection_score_version: "coherence-v1",
    projection_status: "provisional",
    ...overrides,
  };
}

describe("ProjectedCoherencePanel", () => {
  it("renders trusted solid, projected provisional, delta and pending count", () => {
    render(<ProjectedCoherencePanel summary={summary()} />);

    const trusted = screen.getByTestId("coherence-trusted-score");
    expect(trusted).toHaveTextContent("80");
    expect(trusted.dataset.variant).toBe("trusted");

    const projected = screen.getByTestId("coherence-projected-score");
    expect(projected).toHaveTextContent("60");
    expect(projected.dataset.variant).toBe("provisional");
    expect(projected.className).toMatch(/border-dashed/);
    expect(projected.className).toMatch(/opacity-/);
    expect(
      screen.getByText(/Projected if all pending proposals are accepted unchanged/i),
    ).toBeInTheDocument();

    expect(screen.getByTestId("coherence-projected-delta")).toHaveTextContent("−20");
    expect(screen.getByTestId("coherence-pending-count")).toHaveTextContent("2");
    const cta = screen.getByRole("link", { name: /review 2 pending proposals/i });
    expect(cta).toHaveAttribute("href", "/projects/proj-1/review");
  });

  it("renders nothing when no review is pending", () => {
    render(
      <ProjectedCoherencePanel
        summary={summary({
          projected_score: null,
          projected_delta: null,
          pending_review_count: 0,
          projection_status: "none",
        })}
      />,
    );
    expect(screen.queryByTestId("coherence-projected-score")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("region", { name: /trusted and projected coherence/i }),
    ).not.toBeInTheDocument();
  });

  it("first analysis: trusted pending, projected numeric and provisional", () => {
    render(
      <ProjectedCoherencePanel
        summary={summary({
          coherence_score: null,
          global_score: null,
          trusted_score: null,
          projected_score: 72,
          projected_delta: null,
          pending_review_count: 1,
        })}
      />,
    );
    expect(screen.getByTestId("coherence-trusted-score")).toHaveTextContent("—");
    expect(screen.getByTestId("coherence-trusted-score")).not.toHaveTextContent("0");
    expect(screen.getByTestId("coherence-projected-score")).toHaveTextContent("72");
    expect(screen.queryByTestId("coherence-projected-delta")).not.toBeInTheDocument();
  });

  it("shows why a projection is unavailable without hiding pending count", () => {
    render(
      <ProjectedCoherencePanel
        summary={summary({
          projected_score: null,
          projected_delta: null,
          pending_review_count: 1,
          projection_status: "unavailable",
          projection_reason: "score_version_mismatch",
        })}
      />,
    );
    expect(screen.getByTestId("coherence-projected-score")).toHaveTextContent("—");
    expect(screen.getByText(/projection unavailable/i)).toBeInTheDocument();
    expect(screen.getByTestId("coherence-pending-count")).toHaveTextContent("1");
  });
});
