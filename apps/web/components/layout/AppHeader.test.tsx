import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { renderWithProviders, screen } from "@/src/tests/test-utils";
import { AppHeader } from "./AppHeader";

const pathnameState = { value: "/dashboard" };
const appModeState = { mode: "prod" as "demo" | "prod", demoEnvironmentEnabled: false };

vi.mock("@clerk/nextjs", () => ({
  ClerkProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
  useClerk: () => ({
    signOut: vi.fn(),
  }),
  useUser: () => ({
    user: {
      firstName: "Jane",
      lastName: "Doe",
      fullName: "Jane Doe",
      emailAddresses: [{ emailAddress: "jane@example.com" }],
      imageUrl: "",
    },
  }),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => pathnameState.value,
  useSearchParams: () => new URLSearchParams(),
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
  }),
}));

vi.mock("@/stores/app-mode", () => ({
  useAppModeStore: (selector: (state: typeof appModeState) => unknown) =>
    selector(appModeState),
  selectIsDemoMode: (state: typeof appModeState) => state.mode === "demo",
  isExplicitDemoRoute: (pathname: string | null | undefined) =>
    pathname === "/demo" || pathname?.startsWith("/demo/") === true,
}));

vi.mock("@/lib/api/generated", () => ({}));

describe("AppHeader", () => {
  it("renders the header banner and default title", () => {
    pathnameState.value = "/dashboard";
    appModeState.mode = "prod";
    appModeState.demoEnvironmentEnabled = false;
    renderWithProviders(<AppHeader />);

    expect(screen.getByRole("banner")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /dashboard/i }),
    ).toBeInTheDocument();
  });

  it("renders breadcrumb navigation when provided", () => {
    pathnameState.value = "/dashboard";
    appModeState.mode = "prod";
    appModeState.demoEnvironmentEnabled = false;
    renderWithProviders(<AppHeader breadcrumb={["Projects", "Alpha"]} />);

    const nav = screen.getByRole("navigation", { name: /breadcrumb/i });
    expect(nav).toHaveTextContent("Projects");
    expect(nav).toHaveTextContent("Alpha");
  });

  it("exposes accessible controls for search, notifications, and user menu", async () => {
    pathnameState.value = "/dashboard";
    appModeState.mode = "prod";
    appModeState.demoEnvironmentEnabled = false;
    const user = userEvent.setup();
    renderWithProviders(<AppHeader />);

    expect(
      screen.getByRole("textbox", { name: /search/i }),
    ).toBeInTheDocument();

    const notifications = screen.getByRole("button", {
      name: /notifications/i,
    });
    await user.click(notifications);
    expect(
      screen.getByRole("menuitem", { name: /view all notifications/i }),
    ).toBeInTheDocument();

    await user.keyboard("{Escape}");

    const userMenu = screen.getByRole("button", { name: /user menu/i });
    await user.click(userMenu);
    expect(screen.getByRole("menuitem", { name: /profile/i })).toBeInTheDocument();
  });

  it("shows explicit demo badges on demo routes", () => {
    pathnameState.value = "/demo/projects";
    appModeState.mode = "demo";
    appModeState.demoEnvironmentEnabled = true;
    renderWithProviders(<AppHeader title="Projects" />);

    expect(screen.getByText(/demo workspace/i)).toBeInTheDocument();
    expect(screen.getByText(/sample data/i)).toBeInTheDocument();
  });
});
