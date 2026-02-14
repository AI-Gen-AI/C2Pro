import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, waitFor } from "@/src/tests/test-utils";

const pushMock = vi.fn();
const authMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: pushMock,
  }),
}));

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: () => authMock(),
}));

vi.mock("@/components/landing-page-content", () => ({
  default: () => <div>Landing</div>,
}));

import RootPage from "./page";

describe("RootPage", () => {
  beforeEach(() => {
    pushMock.mockReset();
    authMock.mockReset();
  });

  it("redirects authenticated users with null role to default dashboard", async () => {
    authMock.mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
      userRole: null,
    });

    render(<RootPage />);

    await waitFor(() => {
      expect(pushMock).toHaveBeenCalledWith("/dashboard/projects");
    });
  });

  it("shows landing page when user is not authenticated", async () => {
    authMock.mockReturnValue({
      isAuthenticated: false,
      isLoading: false,
      userRole: null,
    });

    const { findByText } = render(<RootPage />);
    expect(await findByText("Landing")).toBeInTheDocument();
  });
});
