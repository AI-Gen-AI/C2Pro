/**
 * Test Suite ID: TASK-1423
 * Route Coverage: canonical dashboard route parity
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders, screen, waitFor } from "@/src/tests/test-utils";
import AppDashboardPage from "./page";

const getProjectsMock = vi.fn();
const getSummaryMock = vi.fn();
const useAuthStoreMock = vi.fn();

vi.mock("@/stores/auth", () => ({
  useAuthStore: (selector: (state: { token: string | null }) => unknown) =>
    useAuthStoreMock(selector),
}));

vi.mock("@/lib/api/services/dashboard", () => ({
  listProjects: (...args: unknown[]) => getProjectsMock(...args),
  getDashboardSummary: (...args: unknown[]) => getSummaryMock(...args),
}));

vi.mock("@/components/coherence/DashboardClient", () => ({
  DashboardClient: ({ projectName }: { projectName: string }) => (
    <div>Dashboard for {projectName}</div>
  ),
}));

describe("AppDashboardPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows a route back to the projects list from the portfolio overview", async () => {
    useAuthStoreMock.mockImplementation(
      (selector: (state: { token: string | null }) => unknown) =>
        selector({ token: "token-123" }),
    );
    getProjectsMock.mockResolvedValue([
      { id: "project-1", name: "Alpha Project" },
    ]);
    getSummaryMock.mockResolvedValue({
      coherence_score: 91,
      sub_scores: { BUDGET: 88 },
      weights_used: { BUDGET: 0.3 },
      alert_count: 2,
      document_count: 4,
      last_updated: null,
    });

    renderWithProviders(<AppDashboardPage />);

    await waitFor(() => {
      expect(getProjectsMock).toHaveBeenCalledTimes(1);
      expect(getSummaryMock).toHaveBeenCalledWith("project-1");
    });

    expect(
      screen.getByRole("link", { name: /back to projects/i }),
    ).toHaveAttribute("href", "/projects");
  });
});
