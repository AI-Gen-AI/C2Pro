import type { ReactNode } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const startMock = vi.fn().mockResolvedValue(undefined);
const pathnameState = { value: "/projects" };

vi.mock("@clerk/nextjs", () => ({
  ClerkProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
  useAuth: () => ({
    isSignedIn: true,
    isLoaded: true,
    getToken: async () => "test-token",
    signOut: async () => undefined,
  }),
  useOrganization: () => ({
    organization: { id: "test-org", name: "Test Org", publicMetadata: {} },
  }),
  useUser: () => ({
    user: {
      id: "user-1",
      firstName: "Test",
      lastName: "User",
      primaryEmailAddress: { emailAddress: "test@example.com" },
      publicMetadata: {},
      unsafeMetadata: {},
    },
  }),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => pathnameState.value,
}));

vi.mock("next-themes", () => ({
  ThemeProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

vi.mock("@tanstack/react-query", () => ({
  QueryClientProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

vi.mock("@/components/providers/AuthSync", () => ({
  AuthSync: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

vi.mock("@/contexts/AuthContext", () => ({
  AuthProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

vi.mock("@/contexts/demo-mode", () => ({
  DemoModeProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

vi.mock("@/components/providers/SentryInit", () => ({
  SentryInit: () => null,
}));

vi.mock("@/lib/api/queryClient", () => ({
  createQueryClient: () => ({ clear: vi.fn() }),
}));

vi.mock("@/mocks/browser", () => ({
  worker: {
    start: startMock,
  },
}));

describe("Providers demo boot boundary", () => {
  beforeEach(() => {
    vi.resetModules();
    startMock.mockClear();
  });

  afterEach(() => {
    delete process.env.NEXT_PUBLIC_APP_MODE;
  });

  it("does not boot MSW on normal routes during demo-enabled developer runs", async () => {
    process.env.NEXT_PUBLIC_APP_MODE = "demo";
    pathnameState.value = "/projects";

    const { Providers } = await import("./providers");

    render(
      <Providers>
        <div>App Content</div>
      </Providers>,
    );

    await waitFor(() => {
      expect(screen.getByText("App Content")).toBeInTheDocument();
    });
    expect(startMock).not.toHaveBeenCalled();
    expect(
      screen.queryByText("Initializing demo environment..."),
    ).not.toBeInTheDocument();
  });

  it("keeps protected production routes off the demo worker and renders app content directly", async () => {
    process.env.NEXT_PUBLIC_APP_MODE = "demo";
    pathnameState.value = "/projects";

    const { Providers } = await import("./providers");

    render(
      <Providers>
        <div>Protected Projects Route</div>
      </Providers>,
    );

    await waitFor(() => {
      expect(screen.getByText("Protected Projects Route")).toBeInTheDocument();
    });
    expect(startMock).not.toHaveBeenCalled();
    expect(
      screen.queryByText("Initializing demo environment..."),
    ).not.toBeInTheDocument();
  });

  it("boots MSW only for explicit /demo routes when demo env is enabled", async () => {
    process.env.NEXT_PUBLIC_APP_MODE = "demo";
    pathnameState.value = "/demo/projects";

    const { Providers } = await import("./providers");

    render(
      <Providers>
        <div>Demo Content</div>
      </Providers>,
    );

    await waitFor(() => {
      expect(startMock).toHaveBeenCalledTimes(1);
    });
    await waitFor(() => {
      expect(screen.getByText("Demo Content")).toBeInTheDocument();
    });
  });
});
