/**
 * Test Suite ID: S3-12
 * Backlog Task: TASK-022
 */
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { renderWithProviders, screen } from "@/src/tests/test-utils";
import DashboardLayout from "./layout";

const pathnameState = { value: "/projects" };
const appModeState = {
  mode: "prod" as "demo" | "prod",
  demoEnvironmentEnabled: false,
};

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

vi.mock("@/components/layout/AppSidebar", () => ({
  AppSidebar: () => <aside aria-label="Primary">Sidebar</aside>,
}));

vi.mock("@/components/layout/AppHeader", () => ({
  AppHeader: () => <header>Header</header>,
}));

vi.mock("@/components/layout/DemoBanner", () => ({
  DemoBanner: ({ children }: { children?: ReactNode }) => (
    <div>{children ?? "Demo"}</div>
  ),
}));

describe("DashboardLayout", () => {
  it("[S3-12-RED-APP-01] exposes a skip link that targets the main content region", () => {
    renderWithProviders(
      <DashboardLayout>
        <div>Protected page content</div>
      </DashboardLayout>,
    );

    const skipLink = screen.getByRole("link", { name: /skip to main content/i });
    expect(skipLink).toHaveAttribute("href", "#main-content");
    expect(screen.getByRole("main")).toHaveAttribute("id", "main-content");
  });
});
