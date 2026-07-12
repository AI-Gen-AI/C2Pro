import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { renderWithProviders, screen } from "@/src/tests/test-utils";
import { ProjectTabs } from "./ProjectTabs";

vi.mock("@clerk/nextjs", () => ({
  ClerkProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

vi.mock("next/navigation", () => ({
  usePathname: () => "/projects/proj_demo_001",
  useSearchParams: () => new URLSearchParams(),
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
  }),
}));

vi.mock("@/lib/api/generated", () => ({}));

describe("ProjectTabs", () => {
  it("renders the 8 project detail tabs with correct links when phase2 modules are off", () => {
    renderWithProviders(<ProjectTabs projectId="proj_demo_001" />);

    const nav = screen.getByRole("navigation", { name: /project tabs/i });
    const links = screen.getAllByRole("link");

    expect(nav).toBeInTheDocument();
    expect(links).toHaveLength(8);
    expect(
      screen.getByRole("link", { name: /overview/i }),
    ).toHaveAttribute("href", "/projects/proj_demo_001");
    expect(
      screen.getByRole("link", { name: /coherence/i }),
    ).toHaveAttribute("href", "/projects/proj_demo_001/coherence");
    expect(
      screen.getByRole("link", { name: /documents/i }),
    ).toHaveAttribute("href", "/projects/proj_demo_001/documents");
    expect(
      screen.getByRole("link", { name: /evidence/i }),
    ).toHaveAttribute("href", "/projects/proj_demo_001/evidence");
    expect(
      screen.getByRole("link", { name: /alerts/i }),
    ).toHaveAttribute("href", "/projects/proj_demo_001/alerts");
    expect(
      screen.getByRole("link", { name: /review/i }),
    ).toHaveAttribute("href", "/projects/proj_demo_001/review");
    expect(
      screen.getByRole("link", { name: /budget/i }),
    ).toHaveAttribute("href", "/projects/proj_demo_001/budget");
    expect(
      screen.getByRole("link", { name: /settings/i }),
    ).toHaveAttribute("href", "/projects/proj_demo_001/settings");

    expect(screen.queryByRole("link", { name: /stakeholders/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /wbs/i })).not.toBeInTheDocument();
  });
});
