import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { renderWithProviders, screen } from "@/src/tests/test-utils";
import { AppHeader } from "./AppHeader";

vi.mock("@clerk/nextjs", () => ({
  ClerkProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard",
  useSearchParams: () => new URLSearchParams(),
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
  }),
}));

vi.mock("@/lib/api/generated", () => ({}));

describe("AppHeader", () => {
  it("renders the header banner and default title", () => {
    renderWithProviders(<AppHeader />);

    expect(screen.getByRole("banner")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /dashboard/i }),
    ).toBeInTheDocument();
  });

  it("renders breadcrumb navigation when provided", () => {
    renderWithProviders(<AppHeader breadcrumb={["Projects", "Alpha"]} />);

    const nav = screen.getByRole("navigation", { name: /breadcrumb/i });
    expect(nav).toHaveTextContent("Projects");
    expect(nav).toHaveTextContent("Alpha");
  });

  it("exposes accessible controls for search, notifications, and user menu", async () => {
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
});
