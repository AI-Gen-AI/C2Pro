import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders, screen } from "@/src/tests/test-utils";
import { AuthProvider, useAuth } from "./AuthContext";

const authStoreState = vi.hoisted(() => ({
  token: "token-123" as string | null,
}));

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
    selector(authStoreState),
}));

vi.mock("@/lib/api/generated", () => ({}));

function TestConsumer() {
  const { isAuthenticated, isLoading, userRole, user } = useAuth();
  return (
    <div>
      <span>{isLoading ? "loading" : "ready"}</span>
      <span>{isAuthenticated ? "signed-in" : "signed-out"}</span>
      <span>{userRole ?? "no-role"}</span>
      <span>{user?.first_name ?? "no-user"}</span>
    </div>
  );
}

describe("AuthContext (Clerk-backed)", () => {
  beforeEach(() => {
    authStoreState.token = "token-123";
  });

  it("exposes auth state derived from Clerk", () => {
    renderWithProviders(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>,
    );

    expect(screen.getByText("ready")).toBeInTheDocument();
    expect(screen.getByText("signed-in")).toBeInTheDocument();
    expect(screen.getByText("tenant_admin")).toBeInTheDocument();
    expect(screen.getByText("Ada")).toBeInTheDocument();
  });

  it("keeps auth in loading state until a signed-in Clerk session has a synced access token", () => {
    authStoreState.token = null;

    renderWithProviders(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>,
    );

    expect(screen.getByText("loading")).toBeInTheDocument();
    expect(screen.getByText("signed-out")).toBeInTheDocument();
  });
});
