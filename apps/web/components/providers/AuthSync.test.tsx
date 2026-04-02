import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders, screen, waitFor } from "@/src/tests/test-utils";
import { AuthSync } from "./AuthSync";

const setAuth = vi.fn();
const clearAuth = vi.fn();
const handleAuthErrorStatus = vi.fn();
const clearCache = vi.fn();
let tenantIdInStore = "tenant-uuid-1";
let organizationId: string | null = "org-1";
let organizationTenantId: string | null = "tenant-uuid-1";
let organizationMemberships: Array<{ organization: { id: string } }> = [];
let isSignedIn = true;
let isLoaded = true;
let getTokenMock = vi.fn().mockResolvedValue("token-123");
const setActiveMock = vi.fn();
const useOrganizationListMock = vi.fn();
const useOrganizationMock = vi.fn();

vi.mock("@clerk/nextjs", () => ({
  useAuth: () => ({
    isSignedIn,
    isLoaded,
    getToken: getTokenMock,
  }),
  useOrganization: () =>
    useOrganizationMock() ?? {
      organization: organizationId
        ? {
            id: organizationId,
            publicMetadata: organizationTenantId ? { tenant_id: organizationTenantId } : {},
          }
        : null,
    },
  useOrganizationList: (...args: unknown[]) =>
    useOrganizationListMock(...args) ?? {
      isLoaded,
      setActive: setActiveMock,
      userMemberships: {
        data: organizationMemberships,
      },
    },
  ClerkProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

vi.mock("@tanstack/react-query", async () => {
  const actual = await vi.importActual<typeof import("@tanstack/react-query")>(
    "@tanstack/react-query",
  );
  return {
    ...actual,
    useQueryClient: () => ({
      clear: clearCache,
    }),
  };
});

vi.mock("@/stores/auth", () => ({
  useAuthStore: (
    selector: (state: {
      setAuth: typeof setAuth;
      clear: typeof clearAuth;
      tenantId: string | null;
    }) => unknown,
  ) => selector({ setAuth, clear: clearAuth, tenantId: tenantIdInStore }),
}));

vi.mock("@/lib/api/client", () => ({
  handleAuthErrorStatus: (...args: unknown[]) => handleAuthErrorStatus(...args),
}));

vi.mock("@/lib/api/generated", () => ({}));

describe("AuthSync", () => {
  beforeEach(() => {
    getTokenMock = vi.fn().mockResolvedValue("token-123");
    setAuth.mockReset();
    clearAuth.mockReset();
    clearCache.mockReset();
    handleAuthErrorStatus.mockReset();
    setActiveMock.mockReset();
    useOrganizationListMock.mockReset();
    useOrganizationMock.mockReset();
    useOrganizationMock.mockImplementation(() => ({
      organization: organizationId
        ? {
            id: organizationId,
            publicMetadata: organizationTenantId ? { tenant_id: organizationTenantId } : {},
          }
        : null,
    }));
    useOrganizationListMock.mockImplementation(() => ({
      isLoaded,
      setActive: setActiveMock,
      userMemberships: {
        data: organizationMemberships,
      },
    }));
    tenantIdInStore = "tenant-uuid-1";
    organizationId = "org-1";
    organizationTenantId = "tenant-uuid-1";
    organizationMemberships = [{ organization: { id: "org-1" } }];
    isSignedIn = true;
    isLoaded = true;
  });

  it("syncs Clerk token and internal tenant UUID into Zustand", async () => {
    renderWithProviders(
      <AuthSync>
        <div>Child</div>
      </AuthSync>,
    );

    expect(screen.getByText("Child")).toBeInTheDocument();
    await waitFor(() =>
      expect(setAuth).toHaveBeenCalledWith({
        token: "token-123",
        tenantId: "tenant-uuid-1",
      }),
    );
  });

  it("clears the query cache on org switch", async () => {
    tenantIdInStore = "tenant-uuid-1";
    organizationId = "org-2";
    organizationTenantId = "tenant-uuid-2";

    renderWithProviders(
      <AuthSync>
        <div>Child</div>
      </AuthSync>,
    );

    await waitFor(() => expect(clearCache).toHaveBeenCalled());
  });

  it("treats missing Clerk tokens as auth failures instead of leaving protected views ambiguous", async () => {
    getTokenMock = vi.fn().mockResolvedValue(null);

    renderWithProviders(
      <AuthSync>
        <div>Child</div>
      </AuthSync>,
    );

    await waitFor(() => {
      expect(handleAuthErrorStatus).toHaveBeenCalledWith(401);
    });
    expect(setAuth).not.toHaveBeenCalled();
  });

  it("clears local auth state immediately when Clerk reports the user is signed out", async () => {
    isSignedIn = false;

    renderWithProviders(
      <AuthSync>
        <div>Child</div>
      </AuthSync>,
    );

    await waitFor(() => {
      expect(clearAuth).toHaveBeenCalled();
    });
    expect(setAuth).not.toHaveBeenCalled();
  });

  it("does not clear the query cache when the tenant remains unchanged", async () => {
    tenantIdInStore = "tenant-uuid-1";
    organizationId = "org-1";
    organizationTenantId = "tenant-uuid-1";

    renderWithProviders(
      <AuthSync>
        <div>Child</div>
      </AuthSync>,
    );

    await waitFor(() => {
      expect(setAuth).toHaveBeenCalledWith({
        token: "token-123",
        tenantId: "tenant-uuid-1",
      });
    });
    expect(clearCache).not.toHaveBeenCalled();
  });

  it("treats token retrieval exceptions as auth failures", async () => {
    getTokenMock = vi.fn().mockRejectedValue(new Error("clerk unavailable"));

    renderWithProviders(
      <AuthSync>
        <div>Child</div>
      </AuthSync>,
    );

    await waitFor(() => {
      expect(handleAuthErrorStatus).toHaveBeenCalledWith(401);
    });
    expect(setAuth).not.toHaveBeenCalled();
  });

  it("auto-activates the only organization membership when no org is active", async () => {
    organizationId = null;
    organizationTenantId = null;
    organizationMemberships = [{ organization: { id: "org-solo" } }];

    renderWithProviders(
      <AuthSync>
        <div>Child</div>
      </AuthSync>,
    );

    await waitFor(() => {
      expect(setActiveMock).toHaveBeenCalledWith({ organization: "org-solo" });
    });
    expect(setAuth).not.toHaveBeenCalled();
  });

  it("does not auto-activate when multiple organization memberships are available", async () => {
    organizationId = null;
    organizationTenantId = null;
    organizationMemberships = [
      { organization: { id: "org-1" } },
      { organization: { id: "org-2" } },
    ];

    renderWithProviders(
      <AuthSync>
        <div>Child</div>
      </AuthSync>,
    );

    await waitFor(() => {
      expect(setAuth).toHaveBeenCalledWith({
        token: "token-123",
        tenantId: null,
      });
    });
    expect(setActiveMock).not.toHaveBeenCalled();
  });

  it("does not subscribe to organization memberships when the user is signed out", async () => {
    isSignedIn = false;

    renderWithProviders(
      <AuthSync>
        <div>Child</div>
      </AuthSync>,
    );

    await waitFor(() => {
      expect(clearAuth).toHaveBeenCalled();
    });
    expect(useOrganizationMock).not.toHaveBeenCalled();
    expect(useOrganizationListMock).not.toHaveBeenCalled();
  });
});
