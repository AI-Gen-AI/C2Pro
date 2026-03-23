import React, { type ReactNode } from "react";
import { describe, expect, it, beforeEach, vi } from "vitest";
import { waitFor } from "@testing-library/react";
import { render } from "@/src/tests/test-utils";
import { AuthSync } from "@/components/providers/AuthSync";
import { useAuthStore } from "@/stores/auth";

const queryClientClearSpy = vi.fn();
const getTokenMock = vi.fn<() => Promise<string>>();
const handleAuthErrorStatus = vi.fn();

let mockIsSignedIn = true;
let mockOrgId: string | null = "org-1";
let mockTenantUuid: string | null = "tenant-uuid-1";

vi.mock("@clerk/nextjs", () => ({
  useAuth: () => ({
    isSignedIn: mockIsSignedIn,
    isLoaded: true,
    getToken: getTokenMock,
  }),
  useOrganization: () => ({
    organization: mockOrgId
      ? {
          id: mockOrgId,
          publicMetadata: mockTenantUuid ? { tenant_id: mockTenantUuid } : {},
        }
      : null,
  }),
  ClerkProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

vi.mock("@tanstack/react-query", async () => {
  const actual = await vi.importActual<typeof import("@tanstack/react-query")>(
    "@tanstack/react-query",
  );
  return {
    ...actual,
    useQueryClient: () => ({ clear: queryClientClearSpy }),
  };
});

vi.mock("@/lib/api/client", () => ({
  handleAuthErrorStatus: (status: number | undefined) => {
    handleAuthErrorStatus(status);
    if (status === 401) {
      useAuthStore.getState().clear();
    }
  },
}));

describe("AuthSync integration", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockIsSignedIn = true;
    mockOrgId = "org-1";
    mockTenantUuid = "tenant-uuid-1";
    getTokenMock.mockResolvedValue("token-123");
    useAuthStore.setState({ token: null, tenantId: null });
  });

  it("syncs Clerk token and internal tenant UUID into auth store", async () => {
    render(
      <AuthSync>
        <div>auth-child</div>
      </AuthSync>,
    );

    await waitFor(() => {
      expect(useAuthStore.getState()).toMatchObject({
        token: "token-123",
        tenantId: "tenant-uuid-1",
      });
    });
  });

  it("clears auth store when user is signed out", async () => {
    useAuthStore.setState({ token: "stale-token", tenantId: "org-stale" });
    mockIsSignedIn = false;

    render(
      <AuthSync>
        <div>auth-child</div>
      </AuthSync>,
    );

    await waitFor(() => {
      expect(useAuthStore.getState()).toMatchObject({
        token: null,
        tenantId: null,
      });
    });
  });

  it("clears query cache when org changes", async () => {
    useAuthStore.setState({ token: "token-123", tenantId: "tenant-uuid-1" });
    mockOrgId = "org-2";
    mockTenantUuid = "tenant-uuid-2";

    render(
      <AuthSync>
        <div>auth-child</div>
      </AuthSync>,
    );

    await waitFor(() => {
      expect(queryClientClearSpy).toHaveBeenCalledTimes(1);
    });
  });

  it("routes missing Clerk tokens through the canonical auth failure path", async () => {
    getTokenMock.mockResolvedValue(null as unknown as string);
    useAuthStore.setState({ token: "stale-token", tenantId: "tenant-uuid-1" });

    render(
      <AuthSync>
        <div>auth-child</div>
      </AuthSync>,
    );

    await waitFor(() => {
      expect(handleAuthErrorStatus).toHaveBeenCalledWith(401);
    });
    expect(useAuthStore.getState()).toMatchObject({
      token: null,
      tenantId: null,
    });
  });
});
