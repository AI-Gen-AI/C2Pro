import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders, screen } from "@/src/tests/test-utils";
import { DemoModeProvider, useDemoMode } from "./demo-mode";

let isSignedIn = true;
let organizationMetadata: Record<string, unknown> = {
  is_demo: true,
};
const useOrganizationMock = vi.hoisted(() => vi.fn());

vi.mock("@clerk/nextjs", () => ({
  useAuth: () => ({
    isSignedIn,
    isLoaded: true,
  }),
  useOrganization: () =>
    useOrganizationMock() ?? {
      organization: {
        id: "org_1",
        publicMetadata: organizationMetadata,
      },
    },
  ClerkProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

function Consumer() {
  const { isDemoMode, productionOrganizationId, isLoading } = useDemoMode();
  return (
    <div>
      <span>{isLoading ? "loading" : "ready"}</span>
      <span>{isDemoMode ? "demo" : "live"}</span>
      <span>{productionOrganizationId ?? "no-org"}</span>
    </div>
  );
}

describe("DemoModeProvider", () => {
  beforeEach(() => {
    isSignedIn = true;
    organizationMetadata = { is_demo: true };
    useOrganizationMock.mockReset();
    useOrganizationMock.mockImplementation(() => ({
      organization: {
        id: "org_1",
        publicMetadata: organizationMetadata,
      },
    }));
  });

  it("reads demo mode from organization metadata when signed in", async () => {
    renderWithProviders(
      <DemoModeProvider>
        <Consumer />
      </DemoModeProvider>,
    );

    expect(await screen.findByText("ready")).toBeInTheDocument();
    expect(screen.getByText("demo")).toBeInTheDocument();
    expect(screen.getByText("org_1")).toBeInTheDocument();
  });

  it("does not call useOrganization when there is no signed-in user", async () => {
    isSignedIn = false;

    renderWithProviders(
      <DemoModeProvider>
        <Consumer />
      </DemoModeProvider>,
    );

    expect(await screen.findByText("ready")).toBeInTheDocument();
    expect(screen.getByText("live")).toBeInTheDocument();
    expect(screen.getByText("no-org")).toBeInTheDocument();
    expect(useOrganizationMock).not.toHaveBeenCalled();
  });
});
