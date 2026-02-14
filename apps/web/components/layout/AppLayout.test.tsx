import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { renderWithProviders, screen } from "@/src/tests/test-utils";
import { AppLayout } from "./AppLayout";

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

describe("AppLayout shell", () => {
  it("renders sidebar, header, and demo banner", () => {
    renderWithProviders(
      <AppLayout title="Projects">
        <div>Content</div>
      </AppLayout>,
    );

    expect(screen.getByRole("complementary")).toBeInTheDocument();
    expect(screen.getByRole("banner")).toBeInTheDocument();
    expect(
      screen.getByRole("status", { name: /demo mode/i }),
    ).toBeInTheDocument();
  });

  it("renders breadcrumb navigation when provided", () => {
    renderWithProviders(
      <AppLayout breadcrumb={["Projects", "Alpha"]}>
        <div>Content</div>
      </AppLayout>,
    );

    const nav = screen.getByRole("navigation", { name: /breadcrumb/i });
    expect(nav).toHaveTextContent("Projects");
    expect(nav).toHaveTextContent("Alpha");
  });

  it("allows collapsing and expanding the sidebar", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <AppLayout>
        <div>Content</div>
      </AppLayout>,
    );

    const toggle = screen.getByRole("button", { name: /collapse sidebar/i });
    await user.click(toggle);
    expect(
      screen.getByRole("button", { name: /expand sidebar/i }),
    ).toBeInTheDocument();
  });
});
