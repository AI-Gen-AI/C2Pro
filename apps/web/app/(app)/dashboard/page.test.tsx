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
const replaceMock = vi.fn();
const useAuthMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    replace: replaceMock,
  }),
}));

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: () => useAuthMock(),
}));

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
    useAuthMock.mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
      userRole: null,
    });
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

  it("shows a guided empty state with Create project CTA when no projects exist", async () => {
    useAuthStoreMock.mockImplementation(
      (selector: (state: { token: string | null }) => unknown) =>
        selector({ token: "token-123" }),
    );
    getProjectsMock.mockResolvedValue([]);

    renderWithProviders(<AppDashboardPage />);

    await waitFor(() => {
      expect(getProjectsMock).toHaveBeenCalledTimes(1);
    });

    expect(screen.getByText(/no projects yet/i)).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /create project/i }),
    ).toHaveAttribute("href", "/projects");
  });

  it("does not show the Create CTA empty state when projects load successfully", async () => {
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
      expect(getSummaryMock).toHaveBeenCalledWith("project-1");
    });

    expect(screen.queryByText(/no projects yet/i)).not.toBeInTheDocument();
  });

  it("shows the load error box for real failures, not the zero-projects state", async () => {
    useAuthStoreMock.mockImplementation(
      (selector: (state: { token: string | null }) => unknown) =>
        selector({ token: "token-123" }),
    );
    getProjectsMock.mockRejectedValue(new Error("Network down"));

    renderWithProviders(<AppDashboardPage />);

    await waitFor(() => {
      expect(screen.getByText(/network down/i)).toBeInTheDocument();
    });

    expect(
      screen.queryByRole("link", { name: /create project/i }),
    ).not.toBeInTheDocument();
  });

  it("redirects c2pro admins to the admin workspace from the dashboard route", async () => {
    useAuthMock.mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
      userRole: "c2pro_admin",
    });
    useAuthStoreMock.mockImplementation(
      (selector: (state: { token: string | null }) => unknown) =>
        selector({ token: "token-123" }),
    );

    renderWithProviders(<AppDashboardPage />);

    await waitFor(() => {
      expect(replaceMock).toHaveBeenCalledWith("/admin/c2pro");
    });
    expect(getProjectsMock).not.toHaveBeenCalled();
  });

  it("redirects tenant admins to the tenant admin workspace from the dashboard route", async () => {
    useAuthMock.mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
      userRole: "tenant_admin",
    });
    useAuthStoreMock.mockImplementation(
      (selector: (state: { token: string | null }) => unknown) =>
        selector({ token: "token-123" }),
    );

    renderWithProviders(<AppDashboardPage />);

    await waitFor(() => {
      expect(replaceMock).toHaveBeenCalledWith("/admin/tenant");
    });
    expect(getProjectsMock).not.toHaveBeenCalled();
  });
});
