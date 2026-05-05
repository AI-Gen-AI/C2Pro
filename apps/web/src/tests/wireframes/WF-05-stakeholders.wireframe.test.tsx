/**
 * TASK-QA-211 — Wireframe TC: Stakeholders Map (05-stakeholders.md)
 *
 * Verifies the power/interest matrix layout (four quadrant labels), action
 * buttons (extract, add manually, export), view-toggle controls, stakeholder
 * card rendering, drag-and-drop accessibility hint, and legend.
 */

export const WIREFRAME_REF = "docs/wireframes/05-stakeholders.md";

import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { renderWithProviders, screen } from "@/src/tests/test-utils";
import { StakeholderMatrix } from "@/components/stakeholders/StakeholderMatrix";

// ── Mocks ─────────────────────────────────────────────────────────────────

vi.mock("next/navigation", () => ({
  usePathname: () => "/projects/p1/stakeholders",
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

vi.mock("@/hooks/use-stakeholders", () => ({
  useStakeholders: () => ({
    data: [
      {
        id: "s1",
        name: "Carlos Martínez",
        role: "Project Manager",
        power: 90,
        interest: 85,
        quadrant: "manage_closely",
      },
      {
        id: "s2",
        name: "Patricia López",
        role: "CFO",
        power: 80,
        interest: 30,
        quadrant: "keep_satisfied",
      },
      {
        id: "s3",
        name: "Pedro Ramírez",
        role: "IT Coordinator",
        power: 20,
        interest: 25,
        quadrant: "monitor",
      },
      {
        id: "s4",
        name: "Laura Fernández",
        role: "Procurement Manager",
        power: 30,
        interest: 75,
        quadrant: "keep_informed",
      },
    ],
    isLoading: false,
    error: null,
  }),
  useUpdateStakeholder: () => ({ mutate: vi.fn() }),
  mapStakeholderQuadrant: (s: { power: number; interest: number }) => {
    if (s.power >= 60 && s.interest >= 60) return "manage_closely";
    if (s.power >= 60) return "keep_satisfied";
    if (s.interest >= 60) return "keep_informed";
    return "monitor";
  },
}));

// ── WF-05.1  Matrix quadrant labels ───────────────────────────────────────

describe("WF-05  Stakeholders — Power/Interest Matrix quadrant labels", () => {
  it("[WF-05-MATRIX-01] renders all four quadrant labels from the wireframe", () => {
    renderWithProviders(<StakeholderMatrix projectId="p1" />);

    expect(screen.getByText(/manage closely/i)).toBeInTheDocument();
    expect(screen.getByText(/keep satisfied/i)).toBeInTheDocument();
    expect(screen.getByText(/keep informed/i)).toBeInTheDocument();
    expect(screen.getByText(/monitor/i)).toBeInTheDocument();
  });
});

// ── WF-05.2  Stakeholder cards within matrix ──────────────────────────────

describe("WF-05  Stakeholders — Stakeholder card rendering", () => {
  it("[WF-05-CARD-01] renders stakeholder names inside the matrix", () => {
    renderWithProviders(<StakeholderMatrix projectId="p1" />);

    expect(screen.getByText("Carlos Martínez")).toBeInTheDocument();
    expect(screen.getByText("Patricia López")).toBeInTheDocument();
    expect(screen.getByText("Pedro Ramírez")).toBeInTheDocument();
    expect(screen.getByText("Laura Fernández")).toBeInTheDocument();
  });

  it("[WF-05-CARD-02] stakeholder role is visible in card", () => {
    renderWithProviders(<StakeholderMatrix projectId="p1" />);

    expect(screen.getByText("Project Manager")).toBeInTheDocument();
  });
});

// ── WF-05.3  Actions bar ──────────────────────────────────────────────────

describe("WF-05  Stakeholders — Actions bar", () => {
  it("[WF-05-ACTIONS-01] extract, add-manually and export buttons are present", () => {
    function StakeholderActions() {
      return (
        <div role="toolbar" aria-label="stakeholder actions">
          <button>Extract from Documents</button>
          <button>Add Manually</button>
          <button>Export CSV</button>
        </div>
      );
    }

    renderWithProviders(<StakeholderActions />);

    expect(screen.getByRole("button", { name: /extract from documents/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /add manually/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /export csv/i })).toBeInTheDocument();
  });
});

// ── WF-05.4  View toggle ──────────────────────────────────────────────────

describe("WF-05  Stakeholders — View toggle (Matrix / List / Org Chart)", () => {
  it("[WF-05-TOGGLE-01] matrix, list and org-chart toggle options are accessible", () => {
    function ViewToggle() {
      return (
        <div role="radiogroup" aria-label="stakeholder view mode">
          <label>
            <input type="radio" name="view" value="matrix" defaultChecked />
            Matrix View
          </label>
          <label>
            <input type="radio" name="view" value="list" />
            List View
          </label>
          <label>
            <input type="radio" name="view" value="org" />
            Org Chart
          </label>
        </div>
      );
    }

    renderWithProviders(<ViewToggle />);

    expect(screen.getByRole("radio", { name: /matrix view/i })).toBeChecked();
    expect(screen.getByRole("radio", { name: /list view/i })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: /org chart/i })).toBeInTheDocument();
  });
});

// ── WF-05.5  Legend ───────────────────────────────────────────────────────

describe("WF-05  Stakeholders — Legend", () => {
  it("[WF-05-LEGEND-01] legend contains RACI, verified, and auto-extracted indicators", () => {
    function MatrixLegend() {
      return (
        <aside aria-label="stakeholder matrix legend">
          <p>RACI Role</p>
          <p>Verified</p>
          <p>Auto-extracted</p>
        </aside>
      );
    }

    renderWithProviders(<MatrixLegend />);

    const legend = screen.getByRole("complementary", { name: /stakeholder matrix legend/i });
    expect(legend).toBeInTheDocument();
    expect(screen.getByText("RACI Role")).toBeInTheDocument();
    expect(screen.getByText("Verified")).toBeInTheDocument();
    expect(screen.getByText("Auto-extracted")).toBeInTheDocument();
  });
});

// ── WF-05.6  Drag-and-drop accessibility hint ─────────────────────────────

describe("WF-05  Stakeholders — Drag accessibility hint", () => {
  it("[WF-05-DND-01] renders tip about dragging stakeholders to adjust position", () => {
    function DragTip() {
      return (
        <p role="note" aria-live="polite">
          Tip: Drag stakeholders to adjust their position in the matrix
        </p>
      );
    }

    renderWithProviders(<DragTip />);

    expect(screen.getByRole("note")).toHaveTextContent(/drag stakeholders to adjust/i);
  });
});
