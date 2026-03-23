import { describe, expect, it, vi, beforeEach } from "vitest";
import { renderWithProviders, screen, waitFor } from "@/src/tests/test-utils";
import DashboardPage from "./page";

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

describe("DashboardPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("waits for the auth token before loading dashboard data", () => {
    useAuthStoreMock.mockImplementation(
      (selector: (state: { token: string | null }) => unknown) =>
        selector({ token: null }),
    );

    renderWithProviders(<DashboardPage />);

    expect(screen.getByText(/authenticating/i)).toBeInTheDocument();
    expect(getProjectsMock).not.toHaveBeenCalled();
    expect(getSummaryMock).not.toHaveBeenCalled();
  });

  it("loads projects and coherence summary after auth is ready", async () => {
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

    renderWithProviders(<DashboardPage />);

    await waitFor(() => {
      expect(getProjectsMock).toHaveBeenCalledTimes(1);
      expect(getSummaryMock).toHaveBeenCalledWith("project-1");
    });

    expect(
      screen.getByText(/dashboard for alpha project/i),
    ).toBeInTheDocument();
  });
});
