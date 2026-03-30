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

vi.mock("@/lib/api/generated/projects/projects", () => ({
  listProjectsApiV1ProjectsGet: (...args: unknown[]) => getProjectsMock(...args),
}));

vi.mock("@/lib/api/generated/coherence-dashboard/coherence-dashboard", () => ({
  getCoherenceDashboardApiCoherenceDashboardProjectIdGet: (...args: unknown[]) =>
    getSummaryMock(...args),
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
    getProjectsMock.mockResolvedValue({
      items: [{ id: "project-1", name: "Alpha Project" }],
      total: 1,
    });
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

  it("shows an empty-project error when no projects are available", async () => {
    useAuthStoreMock.mockImplementation(
      (selector: (state: { token: string | null }) => unknown) =>
        selector({ token: "token-123" }),
    );
    getProjectsMock.mockResolvedValue({ items: [], total: 0 });

    renderWithProviders(<DashboardPage />);

    await waitFor(() =>
      expect(
        screen.getByText(/no projects found\. create a project to see coherence data\./i),
      ).toBeInTheDocument(),
    );
    expect(getSummaryMock).not.toHaveBeenCalled();
  });

  it("shows the backend error message when dashboard loading fails", async () => {
    useAuthStoreMock.mockImplementation(
      (selector: (state: { token: string | null }) => unknown) =>
        selector({ token: "token-123" }),
    );
    getProjectsMock.mockRejectedValue(new Error("dashboard offline"));

    renderWithProviders(<DashboardPage />);

    await waitFor(() =>
      expect(screen.getByText(/dashboard offline/i)).toBeInTheDocument(),
    );
    expect(
      screen.getByText(/verify the backend coherence endpoints are available\./i),
    ).toBeInTheDocument();
  });

  it("falls back to a stable message for non-Error load failures", async () => {
    useAuthStoreMock.mockImplementation(
      (selector: (state: { token: string | null }) => unknown) =>
        selector({ token: "token-123" }),
    );
    getProjectsMock.mockRejectedValue("boom");

    renderWithProviders(<DashboardPage />);

    await waitFor(() =>
      expect(
        screen.getByText(/could not load dashboard data right now\./i),
      ).toBeInTheDocument(),
    );
  });

  it("clears the dashboard when auth is removed after a successful load", async () => {
    let token = "token-123";
    useAuthStoreMock.mockImplementation(
      (selector: (state: { token: string | null }) => unknown) =>
        selector({ token }),
    );
    getProjectsMock.mockResolvedValue({
      items: [{ id: "project-1", name: "Alpha Project" }],
      total: 1,
    });
    getSummaryMock.mockResolvedValue({
      coherence_score: 91,
      sub_scores: { BUDGET: 88 },
      weights_used: { BUDGET: 0.3 },
      alert_count: 2,
      document_count: 4,
      last_updated: null,
    });

    const { rerender } = renderWithProviders(<DashboardPage />);

    await waitFor(() =>
      expect(screen.getByText(/dashboard for alpha project/i)).toBeInTheDocument(),
    );

    token = null as unknown as string;
    rerender(<DashboardPage />);

    expect(screen.getByText(/authenticating/i)).toBeInTheDocument();
  });
});
