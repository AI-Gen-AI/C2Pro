import type { ReactNode } from "react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { renderWithProviders, screen } from "@/src/tests/test-utils";
import { ProtectedRoute } from "./ProtectedRoute";

const push = vi.fn();
let authState = { isAuthenticated: false, isLoading: false };

vi.mock("@clerk/nextjs", () => ({
  ClerkProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
  usePathname: () => "/",
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: () => authState,
}));

vi.mock("@/lib/api/generated", () => ({}));

describe("ProtectedRoute", () => {
  beforeEach(() => {
    push.mockReset();
    authState = { isAuthenticated: false, isLoading: false };
  });

  it("renders a loading state while auth is loading", () => {
    authState = { isAuthenticated: false, isLoading: true };
    renderWithProviders(
      <ProtectedRoute>
        <div>Secret</div>
      </ProtectedRoute>,
    );

    expect(
      screen.getByRole("status", { name: /auth loading/i }),
    ).toBeInTheDocument();
  });

  it("redirects to sign-in when unauthenticated", () => {
    authState = { isAuthenticated: false, isLoading: false };
    renderWithProviders(
      <ProtectedRoute>
        <div>Secret</div>
      </ProtectedRoute>,
    );

    expect(push).toHaveBeenCalledWith("/sign-in");
  });

  it("does not render protected children while redirecting an unauthenticated user", () => {
    authState = { isAuthenticated: false, isLoading: false };
    renderWithProviders(
      <ProtectedRoute>
        <div>Secret</div>
      </ProtectedRoute>,
    );

    expect(screen.queryByText("Secret")).not.toBeInTheDocument();
  });

  it("does not redirect while auth is still resolving after a token loss", () => {
    authState = { isAuthenticated: false, isLoading: true };
    renderWithProviders(
      <ProtectedRoute>
        <div>Secret</div>
      </ProtectedRoute>,
    );

    expect(push).not.toHaveBeenCalled();
  });

  it("renders children when authenticated", () => {
    authState = { isAuthenticated: true, isLoading: false };
    renderWithProviders(
      <ProtectedRoute>
        <div>Secret</div>
      </ProtectedRoute>,
    );

    expect(screen.getByText("Secret")).toBeInTheDocument();
  });

  it("does not redirect authenticated users", () => {
    authState = { isAuthenticated: true, isLoading: false };
    renderWithProviders(
      <ProtectedRoute>
        <div>Secret</div>
      </ProtectedRoute>,
    );

    expect(push).not.toHaveBeenCalled();
  });
});
