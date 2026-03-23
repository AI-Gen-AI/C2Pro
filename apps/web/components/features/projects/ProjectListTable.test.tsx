import type { ReactNode } from "react";
import type { ProjectListItem } from "@/lib/api/contracts";
import { describe, expect, it, vi } from "vitest";
import { renderWithProviders, screen } from "@/src/tests/test-utils";
import { ProjectListTable } from "./ProjectListTable";

vi.mock("@/lib/api/generated", () => ({}));
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

describe("ProjectListTable", () => {
  it("renders project rows with accessible links", () => {
    const projects: ProjectListItem[] = [
      {
        id: "proj_demo_001",
        tenant_id: "tenant-demo",
        name: "Torre Skyline",
        description: "Demo project",
      },
      {
        id: "proj_demo_002",
        tenant_id: "tenant-demo",
        name: "Atlas Plaza",
        description: "Demo project",
      },
    ];

    renderWithProviders(<ProjectListTable projects={projects} />);

    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /torre skyline/i }),
    ).toHaveAttribute("href", "/projects/proj_demo_001");
    expect(screen.getByRole("link", { name: /atlas plaza/i })).toHaveAttribute(
      "href",
      "/projects/proj_demo_002",
    );
  });
});
