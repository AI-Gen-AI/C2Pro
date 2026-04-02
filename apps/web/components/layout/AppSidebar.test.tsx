import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { renderWithProviders, screen } from "@/src/tests/test-utils";
import { AppSidebar } from "./AppSidebar";

const pathnameState = { value: "/projects" };
const organizationState = {
  value: {
    organization: {
      name: "Atlas Ridge",
    },
  },
};

vi.mock("@clerk/nextjs", () => ({
  ClerkProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
  useOrganization: () => organizationState.value,
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

vi.mock("@/lib/api/generated", () => ({}));

describe("AppSidebar", () => {
  it("renders primary navigation with active link state", () => {
    pathnameState.value = "/projects";
    renderWithProviders(<AppSidebar />);

    const nav = screen.getByRole("navigation", { name: /primary/i });
    expect(nav).toBeInTheDocument();

    const activeLink = screen.getByRole("link", { name: /projects/i });
    expect(activeLink).toHaveAttribute("aria-current", "page");
  });

  it("toggles collapsed state via the control button", async () => {
    pathnameState.value = "/projects";
    const user = userEvent.setup();
    renderWithProviders(<AppSidebar />);

    const collapseButton = screen.getByRole("button", {
      name: /collapse sidebar/i,
    });
    expect(collapseButton).toHaveAttribute("aria-expanded", "true");
    expect(collapseButton).toHaveAttribute("aria-controls", "primary-navigation");
    await user.click(collapseButton);

    const expandButton = screen.getByRole("button", { name: /expand sidebar/i });
    expect(expandButton).toBeInTheDocument();
    expect(expandButton).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByRole("complementary", { name: /application sidebar/i })).toBeInTheDocument();
  });

  it("keeps real workspace navigation out of the /demo route space", () => {
    pathnameState.value = "/projects";
    renderWithProviders(<AppSidebar />);

    expect(screen.getByText("Atlas Ridge")).toBeInTheDocument();
    expect(screen.queryByText(/torre skyline/i)).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /projects/i })).toHaveAttribute(
      "href",
      "/projects",
    );
    expect(screen.getByRole("link", { name: /settings/i })).toHaveAttribute(
      "href",
      "/settings",
    );
  });

  it("marks demo route context as sample data only", () => {
    pathnameState.value = "/demo/projects";
    renderWithProviders(<AppSidebar />);

    expect(screen.getByText(/demo workspace/i)).toBeInTheDocument();
    expect(screen.getByText(/sample data only/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /projects/i })).toHaveAttribute(
      "href",
      "/demo/projects",
    );
  });

  it("routes the dashboard nav item to the canonical root path", () => {
    pathnameState.value = "/";
    renderWithProviders(<AppSidebar />);

    expect(screen.getByRole("link", { name: /dashboard/i })).toHaveAttribute(
      "href",
      "/",
    );
    expect(screen.getByRole("link", { name: /dashboard/i })).toHaveAttribute(
      "aria-current",
      "page",
    );
  });

  it("keeps the dashboard nav item active for the legacy /dashboard route during migration", () => {
    pathnameState.value = "/dashboard";
    renderWithProviders(<AppSidebar />);

    expect(screen.getByRole("link", { name: /dashboard/i })).toHaveAttribute(
      "href",
      "/",
    );
    expect(screen.getByRole("link", { name: /dashboard/i })).toHaveAttribute(
      "aria-current",
      "page",
    );
  });

  it("keeps the active projects item readable against the sidebar accent background", () => {
    pathnameState.value = "/projects";
    renderWithProviders(<AppSidebar />);

    expect(screen.getByRole("link", { name: /projects/i })).not.toHaveClass(
      "text-white",
    );
  });
});
