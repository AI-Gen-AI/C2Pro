import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { renderWithProviders, screen, waitFor } from "@/src/tests/test-utils";
import { AuthSync } from "./AuthSync";

const setAuth = vi.fn();
const clearCache = vi.fn();
let tenantIdInStore = "org-1";
let organizationId = "org-1";

vi.mock("@clerk/nextjs", () => ({
  useAuth: () => ({
    isSignedIn: true,
    getToken: vi.fn().mockResolvedValue("token-123"),
  }),
  useOrganization: () => ({
    organization: { id: organizationId },
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
  useAuthStore: (selector: (state: { setAuth: typeof setAuth; tenantId: string | null }) => unknown) =>
    selector({ setAuth, tenantId: tenantIdInStore }),
}));

vi.mock("@/lib/api/generated", () => ({}));

describe("AuthSync", () => {
  it("syncs Clerk token and tenant id into Zustand", async () => {
    renderWithProviders(
      <AuthSync>
        <div>Child</div>
      </AuthSync>,
    );

    expect(screen.getByText("Child")).toBeInTheDocument();
    await waitFor(() =>
      expect(setAuth).toHaveBeenCalledWith({
        token: "token-123",
        tenantId: "org-1",
      }),
    );
  });

  it("clears the query cache on org switch", async () => {
    tenantIdInStore = "org-1";
    organizationId = "org-2";

    renderWithProviders(
      <AuthSync>
        <div>Child</div>
      </AuthSync>,
    );

    await waitFor(() => expect(clearCache).toHaveBeenCalled());
  });
});
