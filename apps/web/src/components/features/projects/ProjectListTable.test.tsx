import type { ReactNode } from "react";
import type { ProjectListItemResponse } from "@/lib/api/generated/models";
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
    const projects: ProjectListItemResponse[] = [
      { id: "proj_demo_001", name: "Torre Skyline", description: "Demo project" },
      { id: "proj_demo_002", name: "Atlas Plaza", description: "Demo project" },
    ];

    renderWithProviders(<ProjectListTable projects={projects} />);

    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /torre skyline/i })).toHaveAttribute(
      "href",
      "/projects/proj_demo_001",
    );
    expect(screen.getByRole("link", { name: /atlas plaza/i })).toHaveAttribute(
      "href",
      "/projects/proj_demo_002",
    );
  });
});
