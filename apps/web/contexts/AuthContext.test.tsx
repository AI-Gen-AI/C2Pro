import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { renderWithProviders, screen } from "@/src/tests/test-utils";
import { AuthProvider, useAuth } from "./AuthContext";

vi.mock("@clerk/nextjs", () => ({
  useAuth: () => ({
    isLoaded: true,
    isSignedIn: true,
    signOut: vi.fn(),
  }),
  useUser: () => ({
    user: {
      id: "user_1",
      firstName: "Ada",
      lastName: "Lovelace",
      primaryEmailAddress: { emailAddress: "ada@example.com" },
      publicMetadata: { role: "tenant_admin" },
    },
  }),
  useOrganization: () => ({
    organization: { id: "org_1", name: "C2Pro" },
  }),
  ClerkProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

vi.mock("@/stores/auth", () => ({
  useAuthStore: (selector: (state: { token: string | null }) => unknown) =>
    selector({ token: "token-123" }),
}));

vi.mock("@/lib/api/generated", () => ({}));

function TestConsumer() {
  const { isAuthenticated, userRole, user } = useAuth();
  return (
    <div>
      <span>{isAuthenticated ? "signed-in" : "signed-out"}</span>
      <span>{userRole ?? "no-role"}</span>
      <span>{user?.first_name ?? "no-user"}</span>
    </div>
  );
}

describe("AuthContext (Clerk-backed)", () => {
  it("exposes auth state derived from Clerk", () => {
    renderWithProviders(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>,
    );

    expect(screen.getByText("signed-in")).toBeInTheDocument();
    expect(screen.getByText("tenant_admin")).toBeInTheDocument();
    expect(screen.getByText("Ada")).toBeInTheDocument();
  });
});
