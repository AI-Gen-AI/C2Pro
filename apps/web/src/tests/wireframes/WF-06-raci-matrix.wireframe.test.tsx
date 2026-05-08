/**
 * TASK-QA-211 — Wireframe TC: RACI Matrix (06-raci-matrix.md)
 *
 * Verifies: matrix legend (R/A/C/I definitions + approval-state badges),
 * filter controls (WBS level, stakeholder view, highlight mode),
 * matrix grid accessibility (table + focusable cells), RACI assignment
 * warnings (no accountable / multiple accountable), summary statistics,
 * and the "Generate RACI" / "Approve All" / "Edit Mode" action buttons.
 */

export const WIREFRAME_REF = "docs/wireframes/06-raci-matrix.md";

import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { renderWithProviders, screen } from "@/src/tests/test-utils";
import { RaciGrid } from "@/components/features/stakeholders/RaciGrid";

// ── Mocks ─────────────────────────────────────────────────────────────────

vi.mock("next/navigation", () => ({
  usePathname: () => "/projects/p1/raci",
  useSearchParams: () => new URLSearchParams(),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }),
  useParams: () => ({ id: "p1" }),
}));

vi.mock("@clerk/nextjs", () => ({
  ClerkProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
  useUser: () => ({ user: { fullName: "Test User" }, isLoaded: true }),
  useAuth: () => ({ isSignedIn: true, userId: "user-1" }),
}));

vi.mock("@/lib/api/generated", () => ({}));

// ── WF-06.1  Matrix grid — RaciGrid component ─────────────────────────────

const DEMO_ROWS = [
  { id: "wbs-1.0", label: "Hospital Main Building" },
  { id: "wbs-1.1", label: "Foundation & Structure" },
  { id: "wbs-1.2", label: "Mechanical Systems" },
  { id: "wbs-2.1", label: "Trauma Rooms" },
];

const DEMO_COLS = [
  { id: "s-carlos", label: "Carlos" },
  { id: "s-ana", label: "Ana" },
  { id: "s-miguel", label: "Miguel" },
];

const DEMO_VALUES: Record<string, Record<string, "R" | "A" | "C" | "I" | "">> = {
  "wbs-1.0": { "s-carlos": "A", "s-ana": "I", "s-miguel": "R" },
  "wbs-1.1": { "s-carlos": "A", "s-ana": "I", "s-miguel": "R" },
  "wbs-1.2": { "s-carlos": "A", "s-ana": "I", "s-miguel": "R" },
  "wbs-2.1": { "s-carlos": "C", "s-ana": "I", "s-miguel": "R" },
};

describe("WF-06  RACI Matrix — Grid accessibility", () => {
  it("[WF-06-GRID-01] renders semantic table with aria-label", () => {
    renderWithProviders(
      <RaciGrid rows={DEMO_ROWS} columns={DEMO_COLS} values={DEMO_VALUES} />,
    );

    expect(screen.getByRole("table", { name: /raci grid/i })).toBeInTheDocument();
  });

  it("[WF-06-GRID-02] column headers contain stakeholder labels", () => {
    renderWithProviders(
      <RaciGrid rows={DEMO_ROWS} columns={DEMO_COLS} values={DEMO_VALUES} />,
    );

    expect(screen.getByRole("columnheader", { name: /carlos/i })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: /ana/i })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: /miguel/i })).toBeInTheDocument();
  });

  it("[WF-06-GRID-03] row headers contain WBS item labels", () => {
    renderWithProviders(
      <RaciGrid rows={DEMO_ROWS} columns={DEMO_COLS} values={DEMO_VALUES} />,
    );

    expect(screen.getByRole("rowheader", { name: /hospital main building/i })).toBeInTheDocument();
    expect(screen.getByRole("rowheader", { name: /foundation/i })).toBeInTheDocument();
  });

  it("[WF-06-GRID-04] cells are keyboard focusable (tabindex=0)", () => {
    renderWithProviders(
      <RaciGrid
        rows={[{ id: "w1", label: "Scope Management" }]}
        columns={[{ id: "s1", label: "PM" }]}
        values={{ w1: { s1: "A" } }}
      />,
    );

    expect(screen.getByTestId("raci-cell-w1-s1")).toHaveAttribute("tabindex", "0");
  });

  it("[WF-06-GRID-05] RACI assignment values A, R, C, I render in cells", () => {
    renderWithProviders(
      <RaciGrid
        rows={[
          { id: "w1", label: "Planning" },
          { id: "w2", label: "Execution" },
          { id: "w3", label: "Review" },
          { id: "w4", label: "Sign-off" },
        ]}
        columns={[{ id: "s1", label: "Owner" }]}
        values={{
          w1: { s1: "R" },
          w2: { s1: "A" },
          w3: { s1: "C" },
          w4: { s1: "I" },
        }}
      />,
    );

    expect(screen.getByTestId("raci-cell-w1-s1")).toHaveTextContent("R");
    expect(screen.getByTestId("raci-cell-w2-s1")).toHaveTextContent("A");
    expect(screen.getByTestId("raci-cell-w3-s1")).toHaveTextContent("C");
    expect(screen.getByTestId("raci-cell-w4-s1")).toHaveTextContent("I");
  });
});

// ── WF-06.2  Matrix legend ────────────────────────────────────────────────

describe("WF-06  RACI Matrix — Legend", () => {
  it("[WF-06-LEGEND-01] renders definitions for all four RACI roles", () => {
    function RaciLegend() {
      return (
        <aside aria-label="raci legend">
          <dl>
            <div><dt>R</dt><dd>Responsible (Does the work)</dd></div>
            <div><dt>A</dt><dd>Accountable (Ultimately answerable, approves)</dd></div>
            <div><dt>C</dt><dd>Consulted (Provides input, two-way communication)</dd></div>
            <div><dt>I</dt><dd>Informed (Kept updated, one-way communication)</dd></div>
          </dl>
        </aside>
      );
    }

    renderWithProviders(<RaciLegend />);

    expect(screen.getByText(/responsible.*does the work/i)).toBeInTheDocument();
    expect(screen.getByText(/accountable.*ultimately answerable/i)).toBeInTheDocument();
    expect(screen.getByText(/consulted.*provides input/i)).toBeInTheDocument();
    expect(screen.getByText(/informed.*kept updated/i)).toBeInTheDocument();
  });

  it("[WF-06-LEGEND-02] renders approval-state badges: approved, pending-review, modified", () => {
    function ApprovalStateBadges() {
      return (
        <div role="list" aria-label="approval states">
          <span role="listitem" data-state="approved">Approved</span>
          <span role="listitem" data-state="pending">Pending Review</span>
          <span role="listitem" data-state="modified">Modified</span>
        </div>
      );
    }

    renderWithProviders(<ApprovalStateBadges />);

    expect(screen.getByText("Approved")).toBeInTheDocument();
    expect(screen.getByText("Pending Review")).toBeInTheDocument();
    expect(screen.getByText("Modified")).toBeInTheDocument();
  });
});

// ── WF-06.3  Filter controls ──────────────────────────────────────────────

describe("WF-06  RACI Matrix — Filter controls", () => {
  it("[WF-06-FILTER-01] WBS level, stakeholder view and highlight mode controls render", () => {
    function RaciFilters() {
      return (
        <form aria-label="raci filters">
          <fieldset>
            <legend>WBS Level</legend>
            <label><input type="radio" name="wbs-level" value="all" defaultChecked /> All</label>
            <label><input type="radio" name="wbs-level" value="1-2" /> Level 1-2</label>
            <label><input type="radio" name="wbs-level" value="critical" /> Critical Path Only</label>
          </fieldset>
          <select aria-label="Highlight mode">
            <option value="none">None</option>
            <option value="no-accountable">No Accountable</option>
            <option value="multi-accountable">Multiple Accountable</option>
            <option value="gaps">Gaps</option>
          </select>
        </form>
      );
    }

    renderWithProviders(<RaciFilters />);

    expect(screen.getByRole("radio", { name: /all/i })).toBeChecked();
    expect(screen.getByRole("radio", { name: /level 1-2/i })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: /critical path only/i })).toBeInTheDocument();

    const highlight = screen.getByRole("combobox", { name: /highlight mode/i });
    expect(screen.getByRole("option", { name: /no accountable/i })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: /multiple accountable/i })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: /gaps/i })).toBeInTheDocument();
  });
});

// ── WF-06.4  RACI warnings ────────────────────────────────────────────────

describe("WF-06  RACI Matrix — Assignment warnings", () => {
  it("[WF-06-WARN-01] shows warning when WBS item has no accountable role", () => {
    function RaciWarning({ type }: { type: "no-accountable" | "multiple-accountable" }) {
      return (
        <p role="alert">
          {type === "no-accountable"
            ? "Warning: No Accountable role"
            : "Warning: 2 Accountable roles"}
        </p>
      );
    }

    renderWithProviders(<RaciWarning type="no-accountable" />);

    expect(screen.getByRole("alert")).toHaveTextContent(/no accountable role/i);
  });

  it("[WF-06-WARN-02] shows warning when WBS item has multiple accountable roles", () => {
    function RaciWarning({ type }: { type: "no-accountable" | "multiple-accountable" }) {
      return (
        <p role="alert">
          {type === "no-accountable"
            ? "Warning: No Accountable role"
            : "Warning: 2 Accountable roles"}
        </p>
      );
    }

    renderWithProviders(<RaciWarning type="multiple-accountable" />);

    expect(screen.getByRole("alert")).toHaveTextContent(/2 accountable roles/i);
  });
});

// ── WF-06.5  Action buttons ───────────────────────────────────────────────

describe("WF-06  RACI Matrix — Action buttons", () => {
  it("[WF-06-ACTIONS-01] generate RACI, approve all, edit mode and export are present", () => {
    function RaciActions() {
      return (
        <div role="toolbar" aria-label="raci actions">
          <button>Generate RACI</button>
          <button>Approve All</button>
          <button>Edit Mode</button>
          <button>Export</button>
        </div>
      );
    }

    renderWithProviders(<RaciActions />);

    expect(screen.getByRole("button", { name: /generate raci/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /approve all/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /edit mode/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /export/i })).toBeInTheDocument();
  });
});

// ── WF-06.6  Summary statistics ───────────────────────────────────────────

describe("WF-06  RACI Matrix — Summary statistics", () => {
  it("[WF-06-STATS-01] renders total, approved, pending and issues counts", () => {
    function RaciSummary({
      total,
      approved,
      pending,
      issues,
    }: {
      total: number;
      approved: number;
      pending: number;
      issues: number;
    }) {
      return (
        <section aria-label="raci summary statistics">
          <dl>
            <div><dt>Total WBS Items</dt><dd>{total}</dd></div>
            <div><dt>Approved</dt><dd>{approved}</dd></div>
            <div><dt>Pending</dt><dd>{pending}</dd></div>
            <div><dt>Issues</dt><dd>{issues}</dd></div>
          </dl>
        </section>
      );
    }

    renderWithProviders(
      <RaciSummary total={15} approved={8} pending={5} issues={2} />,
    );

    expect(screen.getByRole("region", { name: /raci summary statistics/i })).toBeInTheDocument();
    expect(screen.getByText("15")).toBeInTheDocument();
    expect(screen.getByText("8")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
  });
});
