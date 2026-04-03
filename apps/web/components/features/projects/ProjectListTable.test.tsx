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

  it("renders the empty state when no projects are available", () => {
    renderWithProviders(<ProjectListTable projects={[]} />);

    expect(screen.getByText(/no projects yet/i)).toBeInTheDocument();
    expect(
      screen.getByText(/create your first project to start tracking coherence/i),
    ).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("shows em dash fallbacks for missing description and code", () => {
    const projects: ProjectListItem[] = [
      {
        id: "proj_demo_003",
        tenant_id: "tenant-demo",
        name: "No Metadata Project",
      },
    ];

    renderWithProviders(<ProjectListTable projects={projects} />);

    expect(screen.getByRole("link", { name: /no metadata project/i })).toHaveAttribute(
      "href",
      "/projects/proj_demo_003",
    );
    expect(screen.getAllByText("—").length).toBeGreaterThanOrEqual(2);
  });

  it("renders table headers for project, description, and code", () => {
    const projects: ProjectListItem[] = [
      {
        id: "proj_demo_004",
        tenant_id: "tenant-demo",
        name: "Header Check",
        description: "Header coverage",
        code: "HDR-001",
      },
    ];

    renderWithProviders(<ProjectListTable projects={projects} />);

    expect(screen.getByRole("columnheader", { name: /project/i })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: /description/i })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: /code/i })).toBeInTheDocument();
  });

  it("renders coherence and alert trend deltas with directional indicators", () => {
    const projects: ProjectListItem[] = [
      {
        id: "proj_demo_005",
        tenant_id: "tenant-demo",
        name: "Trend Check",
        description: "Signals",
        code: "TRD-001",
        status: "active",
        coherence_score: 78,
        coherence_score_delta: 4,
        alert_count: 7,
        alert_count_delta: -2,
      },
    ];

    renderWithProviders(<ProjectListTable projects={projects} />);

    expect(screen.getByText("78")).toBeInTheDocument();
    expect(screen.getByText("7")).toBeInTheDocument();
    expect(screen.getByText(/▲\s*\+4/i)).toBeInTheDocument();
    expect(screen.getByText(/▼\s*-2/i)).toBeInTheDocument();
  });
});
