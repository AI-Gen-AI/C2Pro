/**
 * Test Suite ID: TASK-021
 * Route Coverage: project coherence page uses fetch-safe service loaders
 */
import { renderWithProviders, screen } from "@/src/tests/test-utils";
import { describe, expect, it, vi, beforeEach } from "vitest";
import ProjectCoherencePage from "./page";

const getCoherenceDashboardMock = vi.fn();
const getTokenMock = vi.fn();

vi.mock("@/lib/api/services/dashboard", () => ({
  getDashboardSummary: (...args: unknown[]) => getCoherenceDashboardMock(...args),
}));

vi.mock("@clerk/nextjs/server", () => ({
  auth: async () => ({
    getToken: getTokenMock,
  }),
}));

vi.mock("@/components/coherence/CoherenceClient", () => ({
  CoherenceClient: ({ summary }: { summary: { coherence_score: number } }) => (
    <div>Coherence summary {summary.coherence_score}</div>
  ),
}));

describe("ProjectCoherencePage", () => {
  beforeEach(() => {
    getCoherenceDashboardMock.mockReset();
    getTokenMock.mockReset();
    getTokenMock.mockResolvedValue("clerk-server-token");
  });

  it("loads coherence data through the dashboard service with the Clerk server token", async () => {
    getCoherenceDashboardMock.mockResolvedValue({
      project_id: "proj-1",
      tenant_id: "tenant-1",
      coherence_score: 87,
      global_score: 87,
      sub_scores: { BUDGET: 84 },
      weights_used: { BUDGET: 0.3 },
      alert_count: 2,
      document_count: 4,
      methodology_version: "v1",
      last_updated: null,
    });

    renderWithProviders(await ProjectCoherencePage({ params: Promise.resolve({ id: "proj-1" }) }));

    expect(getCoherenceDashboardMock).toHaveBeenCalledWith("proj-1", {
      server: true,
      headers: {
        Authorization: "Bearer clerk-server-token",
      },
    });
    expect(screen.getByText(/coherence summary 87/i)).toBeInTheDocument();
  });

  it("renders the empty coherence state without calling the API when no Clerk token is available", async () => {
    getTokenMock.mockResolvedValue(null);

    renderWithProviders(await ProjectCoherencePage({ params: Promise.resolve({ id: "proj-1" }) }));

    expect(getCoherenceDashboardMock).not.toHaveBeenCalled();
    expect(screen.getByText(/no coherence data yet/i)).toBeInTheDocument();
  });

  it("shows the backend error banner when coherence loading fails", async () => {
    getCoherenceDashboardMock.mockRejectedValue(new Error("coherence offline"));

    renderWithProviders(await ProjectCoherencePage({ params: Promise.resolve({ id: "proj-1" }) }));

    expect(screen.getByText(/coherence offline/i)).toBeInTheDocument();
  });
});
