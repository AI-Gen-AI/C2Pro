import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
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

  it("redirects to login when unauthenticated", () => {
    authState = { isAuthenticated: false, isLoading: false };
    renderWithProviders(
      <ProtectedRoute>
        <div>Secret</div>
      </ProtectedRoute>,
    );

    expect(push).toHaveBeenCalledWith("/login");
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
});
