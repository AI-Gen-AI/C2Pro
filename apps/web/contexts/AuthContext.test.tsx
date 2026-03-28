import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders, screen } from "@/src/tests/test-utils";
import { AuthProvider, useAuth, type ServiceTier } from "./AuthContext";

const authStoreState = vi.hoisted(() => ({
  token: "token-123" as string | null,
}));
const signOutMock = vi.hoisted(() => vi.fn());
let isLoaded = true;
let isSignedIn = true;
let organizationMetadata: Record<string, unknown> = {
  tenant_id: "tenant-uuid-1",
  is_demo: true,
  tier: "enterprise",
};
let userData: {
  id: string;
  firstName: string;
  lastName: string;
  primaryEmailAddress: { emailAddress: string };
  publicMetadata: { role?: string };
  unsafeMetadata?: { role?: string };
} | null = {
  id: "user_1",
  firstName: "Ada",
  lastName: "Lovelace",
  primaryEmailAddress: { emailAddress: "ada@example.com" },
  publicMetadata: { role: "tenant_admin" },
};
let latestAuth: {
  logout: () => Promise<void>;
  login: () => Promise<void>;
  register: () => Promise<void>;
  serviceTier: ServiceTier;
} | null = null;

vi.mock("@clerk/nextjs", () => ({
  useAuth: () => ({
    isLoaded,
    isSignedIn,
    signOut: signOutMock,
  }),
  useUser: () => ({
    user: userData,
  }),
  useOrganization: () => ({
    organization: {
      id: "org_1",
      name: "C2Pro",
      publicMetadata: organizationMetadata,
    },
  }),
  ClerkProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

vi.mock("@/stores/auth", () => ({
  useAuthStore: (selector: (state: { token: string | null }) => unknown) =>
    selector(authStoreState),
}));

vi.mock("@/lib/api/generated", () => ({}));

function TestConsumer() {
  const auth = useAuth();
  latestAuth = auth;
  const {
    isAuthenticated,
    isLoading,
    userRole,
    user,
    tenantId,
    isDemoMode,
    serviceTier,
    isAuthorized,
    logout,
    login,
    register,
  } = useAuth();
  return (
    <div>
      <span>{isLoading ? "loading" : "ready"}</span>
      <span>{isAuthenticated ? "signed-in" : "signed-out"}</span>
      <span>{userRole ?? "no-role"}</span>
      <span>{user?.first_name ?? "no-user"}</span>
      <span>{tenantId ?? "no-tenant"}</span>
      <span>{isDemoMode ? "demo" : "live"}</span>
      <span>{serviceTier}</span>
      <span>{isAuthorized ? "authorized" : "unauthorized"}</span>
      <button onClick={() => void logout()}>logout</button>
      <button
        onClick={() => {
          void login().catch(() => {});
        }}
      >
        login
      </button>
      <button
        onClick={() => {
          void register().catch(() => {});
        }}
      >
        register
      </button>
    </div>
  );
}

describe("AuthContext (Clerk-backed)", () => {
  beforeEach(() => {
    authStoreState.token = "token-123";
    signOutMock.mockReset();
    isLoaded = true;
    isSignedIn = true;
    organizationMetadata = {
      tenant_id: "tenant-uuid-1",
      is_demo: true,
      tier: "enterprise",
    };
    userData = {
      id: "user_1",
      firstName: "Ada",
      lastName: "Lovelace",
      primaryEmailAddress: { emailAddress: "ada@example.com" },
      publicMetadata: { role: "tenant_admin" },
    };
    latestAuth = null;
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
    expect(screen.getByText("tenant-uuid-1")).toBeInTheDocument();
    expect(screen.getByText("demo")).toBeInTheDocument();
    expect(screen.getByText("enterprise")).toBeInTheDocument();
    expect(screen.getByText("authorized")).toBeInTheDocument();
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
    expect(screen.getByText("unauthorized")).toBeInTheDocument();
  });

  it("falls back to a free live workspace when organization metadata is absent or invalid", () => {
    organizationMetadata = {};

    renderWithProviders(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>,
    );

    expect(screen.getByText("no-tenant")).toBeInTheDocument();
    expect(screen.getByText("live")).toBeInTheDocument();
    expect(screen.getByText("free")).toBeInTheDocument();
    expect(screen.getByText("unauthorized")).toBeInTheDocument();
  });

  it("exposes signed-out state when Clerk has no active session", () => {
    isSignedIn = false;
    userData = null;

    renderWithProviders(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>,
    );

    expect(screen.getByText("ready")).toBeInTheDocument();
    expect(screen.getByText("signed-out")).toBeInTheDocument();
    expect(screen.getByText("no-user")).toBeInTheDocument();
  });

  it("delegates logout to Clerk signOut", async () => {
    renderWithProviders(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>,
    );

    screen.getByRole("button", { name: "logout" }).click();
    expect(signOutMock).toHaveBeenCalled();
  });

  it("rejects direct login and register calls in favor of Clerk components", async () => {
    renderWithProviders(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>,
    );

    expect(latestAuth).not.toBeNull();
    await expect(latestAuth!.login()).rejects.toThrow(/clerk signin/i);
    await expect(latestAuth!.register()).rejects.toThrow(/clerk signup/i);
  });
});
