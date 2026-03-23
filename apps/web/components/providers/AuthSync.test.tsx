import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders, screen, waitFor } from "@/src/tests/test-utils";
import { AuthSync } from "./AuthSync";

const setAuth = vi.fn();
const clearAuth = vi.fn();
const handleAuthErrorStatus = vi.fn();
const clearCache = vi.fn();
let tenantIdInStore = "tenant-uuid-1";
let organizationId = "org-1";
let organizationTenantId = "tenant-uuid-1";
let getTokenMock = vi.fn().mockResolvedValue("token-123");

vi.mock("@clerk/nextjs", () => ({
  useAuth: () => ({
    isSignedIn: true,
    isLoaded: true,
    getToken: getTokenMock,
  }),
  useOrganization: () => ({
    organization: {
      id: organizationId,
      publicMetadata: { tenant_id: organizationTenantId },
    },
  }),
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
    tenantIdInStore = "tenant-uuid-1";
    organizationId = "org-1";
    organizationTenantId = "tenant-uuid-1";
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
});
