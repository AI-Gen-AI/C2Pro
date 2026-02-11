import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { renderWithProviders, screen } from "@/src/tests/test-utils";
import { AppSidebar } from "./AppSidebar";

vi.mock("@clerk/nextjs", () => ({
  ClerkProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

vi.mock("next/navigation", () => ({
  usePathname: () => "/projects",
  useSearchParams: () => new URLSearchParams(),
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
  }),
}));

vi.mock("@/lib/api/generated", () => ({}));

describe("AppSidebar", () => {
  it("renders primary navigation with active link state", () => {
    renderWithProviders(<AppSidebar />);

    const nav = screen.getByRole("navigation", { name: /primary/i });
    expect(nav).toBeInTheDocument();

    const activeLink = screen.getByRole("link", { name: /projects/i });
    expect(activeLink).toHaveAttribute("aria-current", "page");
  });

  it("toggles collapsed state via the control button", async () => {
    const user = userEvent.setup();
    renderWithProviders(<AppSidebar />);

    const collapseButton = screen.getByRole("button", {
      name: /collapse sidebar/i,
    });
    await user.click(collapseButton);

    expect(
      screen.getByRole("button", { name: /expand sidebar/i }),
    ).toBeInTheDocument();
  });
});
