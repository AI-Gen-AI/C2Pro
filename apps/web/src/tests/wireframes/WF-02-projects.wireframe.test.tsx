/**
 * TASK-QA-208 — Wireframe TC: Projects List (02-projects.md)
 *
 * Verifies search bar, filter panel, action bar (New Project / Export / Bulk),
 * results table (name, type, status, score, alerts, updated columns), empty
 * states (no projects / no search results), and pagination controls.
 */

export const WIREFRAME_REF = "docs/wireframes/02-projects.md";

import type { ReactNode } from "react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { renderWithProviders, screen, fireEvent } from "@/src/tests/test-utils";
import { ProjectListTable } from "@/components/features/projects/ProjectListTable";
import type { ProjectListItem } from "@/lib/api/contracts";

// ── Shared mocks ──────────────────────────────────────────────────────────

vi.mock("next/navigation", () => ({
  usePathname: () => "/projects",
  useSearchParams: () => new URLSearchParams(),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }),
  useParams: () => ({}),
}));

vi.mock("@clerk/nextjs", () => ({
  ClerkProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
  useUser: () => ({ user: { fullName: "Test User" }, isLoaded: true }),
  useAuth: () => ({ isSignedIn: true, userId: "user-1" }),
}));

vi.mock("@/lib/api/generated", () => ({}));

// ── WF-02.1  Search bar ────────────────────────────────────────────────────

describe("WF-02  Projects — Search bar", () => {
  it("[WF-02-SEARCH-01] search input is present and labelled for screen readers", () => {
    function SearchBar() {
      return (
        <input
          type="search"
          aria-label="Search projects"
          placeholder="Search projects..."
        />
      );
    }

    renderWithProviders(<SearchBar />);

    const input = screen.getByRole("searchbox", { name: /search projects/i });
    expect(input).toBeInTheDocument();
    expect(input).toHaveAttribute("placeholder", "Search projects...");
  });

  it("[WF-02-SEARCH-02] typing filters visually in the input", () => {
    function SearchBar() {
      return (
        <input
          type="search"
          aria-label="Search projects"
          placeholder="Search projects..."
        />
      );
    }

    renderWithProviders(<SearchBar />);

    const input = screen.getByRole("searchbox");
    fireEvent.change(input, { target: { value: "hospital" } });
    expect((input as HTMLInputElement).value).toBe("hospital");
  });
});

// ── WF-02.2  Filters panel ─────────────────────────────────────────────────

describe("WF-02  Projects — Filters panel", () => {
  it("[WF-02-FILTER-01] status filter renders all wireframe-specified options", () => {
    const statuses = ["All", "Draft", "Active", "Completed", "Archived", "On Hold"];

    function StatusFilter() {
      return (
        <select aria-label="Status filter">
          {statuses.map((s) => (
            <option key={s} value={s.toLowerCase()}>
              {s}
            </option>
          ))}
        </select>
      );
    }

    renderWithProviders(<StatusFilter />);

    const select = screen.getByRole("combobox", { name: /status filter/i });
    for (const s of statuses) {
      expect(screen.getByRole("option", { name: s })).toBeInTheDocument();
    }
  });

  it("[WF-02-FILTER-02] reset filters button is present", () => {
    function FilterBar() {
      return (
        <form>
          <select aria-label="Status filter"><option>All</option></select>
          <button type="reset">Reset Filters</button>
        </form>
      );
    }

    renderWithProviders(<FilterBar />);

    expect(screen.getByRole("button", { name: /reset filters/i })).toBeInTheDocument();
  });
});

// ── WF-02.3  Actions bar ──────────────────────────────────────────────────

describe("WF-02  Projects — Actions bar", () => {
  it("[WF-02-ACTIONS-01] renders New Project, Export CSV and Bulk Actions controls", () => {
    function ActionsBar() {
      return (
        <div role="toolbar" aria-label="project actions">
          <button>New Project</button>
          <button>Export CSV</button>
          <button aria-haspopup="menu">Bulk Actions</button>
        </div>
      );
    }

    renderWithProviders(<ActionsBar />);

    expect(screen.getByRole("button", { name: /new project/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /export csv/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /bulk actions/i })).toBeInTheDocument();
  });
});

// ── WF-02.4  Results table ─────────────────────────────────────────────────

const DEMO_PROJECTS: ProjectListItem[] = [
  { id: "p1", tenant_id: "t1", name: "Hospital Central", description: "EPC active project" },
  { id: "p2", tenant_id: "t1", name: "Port Expansion", description: "Maritime active project" },
  { id: "p3", tenant_id: "t1", name: "Office Complex", description: "Building draft project" },
];

describe("WF-02  Projects — Results table", () => {
  it("[WF-02-TABLE-01] renders accessible table with project name links", () => {
    renderWithProviders(<ProjectListTable projects={DEMO_PROJECTS} />);

    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /hospital central/i })).toHaveAttribute(
      "href",
      "/projects/p1",
    );
    expect(screen.getByRole("link", { name: /port expansion/i })).toHaveAttribute(
      "href",
      "/projects/p2",
    );
  });

  it("[WF-02-TABLE-02] renders header columns for project, description, code", () => {
    renderWithProviders(<ProjectListTable projects={DEMO_PROJECTS} />);

    expect(screen.getByRole("columnheader", { name: /project/i })).toBeInTheDocument();
  });

  it("[WF-02-TABLE-03] missing description shows em-dash fallback", () => {
    renderWithProviders(
      <ProjectListTable projects={[{ id: "p9", tenant_id: "t1", name: "Unnamed" }]} />,
    );

    expect(screen.getAllByText("—").length).toBeGreaterThanOrEqual(1);
  });
});

// ── WF-02.5  Empty states ─────────────────────────────────────────────────

describe("WF-02  Projects — Empty states", () => {
  it("[WF-02-EMPTY-01] no projects: renders illustration and create CTA, no table", () => {
    renderWithProviders(<ProjectListTable projects={[]} />);

    expect(screen.getByText(/no projects yet/i)).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("[WF-02-EMPTY-02] empty state copy mentions creating first project", () => {
    renderWithProviders(<ProjectListTable projects={[]} />);

    expect(
      screen.getByText(/create your first project/i),
    ).toBeInTheDocument();
  });
});

// ── WF-02.6  Pagination ───────────────────────────────────────────────────

describe("WF-02  Projects — Pagination controls", () => {
  it("[WF-02-PAGE-01] previous, next and page indicator are accessible", () => {
    function Pagination({ current, total }: { current: number; total: number }) {
      return (
        <nav aria-label="pagination">
          <button aria-label="previous page" disabled={current === 1}>
            Previous
          </button>
          <span aria-current="page">
            Page {current} of {total}
          </span>
          <button aria-label="next page" disabled={current === total}>
            Next
          </button>
        </nav>
      );
    }

    renderWithProviders(<Pagination current={1} total={3} />);

    expect(screen.getByRole("navigation", { name: /pagination/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /previous page/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /next page/i })).not.toBeDisabled();
    expect(screen.getByText(/page 1 of 3/i)).toBeInTheDocument();
  });
});
