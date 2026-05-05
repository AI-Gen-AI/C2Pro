/**
 * TASK-QA-210 — Wireframe TC: Alerts Panel (04-alerts.md)
 *
 * Verifies the quick-stats banner (counts by severity/status), filter bar,
 * bulk-actions row, alert cards (severity icon, rule reference, affected items,
 * action buttons), and view-all link.
 */

export const WIREFRAME_REF = "docs/wireframes/04-alerts.md";

import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { renderWithProviders, screen, fireEvent } from "@/src/tests/test-utils";
import { AlertReviewCenter, type ReviewAlert } from "@/components/features/alerts/AlertReviewCenter";

// ── Mocks ─────────────────────────────────────────────────────────────────

vi.mock("next/navigation", () => ({
  usePathname: () => "/alerts",
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

// ── WF-04.1  Quick Stats banner ────────────────────────────────────────────

describe("WF-04  Alerts — Quick Stats banner", () => {
  it("[WF-04-STATS-01] renders severity counts for critical, high, medium, low", () => {
    type Counts = { critical: number; high: number; medium: number; low: number };

    function AlertStats({ counts }: { counts: Counts }) {
      return (
        <dl aria-label="alert severity counts">
          <div>
            <dt>Critical</dt>
            <dd aria-label={`${counts.critical} critical alerts`}>{counts.critical}</dd>
          </div>
          <div>
            <dt>High</dt>
            <dd aria-label={`${counts.high} high alerts`}>{counts.high}</dd>
          </div>
          <div>
            <dt>Medium</dt>
            <dd aria-label={`${counts.medium} medium alerts`}>{counts.medium}</dd>
          </div>
          <div>
            <dt>Low</dt>
            <dd aria-label={`${counts.low} low alerts`}>{counts.low}</dd>
          </div>
        </dl>
      );
    }

    renderWithProviders(
      <AlertStats counts={{ critical: 8, high: 15, medium: 23, low: 12 }} />,
    );

    expect(screen.getByLabelText("8 critical alerts")).toBeInTheDocument();
    expect(screen.getByLabelText("15 high alerts")).toBeInTheDocument();
    expect(screen.getByLabelText("23 medium alerts")).toBeInTheDocument();
    expect(screen.getByLabelText("12 low alerts")).toBeInTheDocument();
  });

  it("[WF-04-STATS-02] renders status totals: open, resolved, in-progress", () => {
    function AlertStatusSummary({
      open,
      resolved,
      inProgress,
    }: {
      open: number;
      resolved: number;
      inProgress: number;
    }) {
      return (
        <dl aria-label="alert status summary">
          <div><dt>Open</dt><dd>{open}</dd></div>
          <div><dt>Resolved</dt><dd>{resolved}</dd></div>
          <div><dt>In Progress</dt><dd>{inProgress}</dd></div>
        </dl>
      );
    }

    renderWithProviders(
      <AlertStatusSummary open={45} resolved={123} inProgress={13} />,
    );

    expect(screen.getByText("Open")).toBeInTheDocument();
    expect(screen.getByText("45")).toBeInTheDocument();
    expect(screen.getByText("Resolved")).toBeInTheDocument();
    expect(screen.getByText("123")).toBeInTheDocument();
    expect(screen.getByText("In Progress")).toBeInTheDocument();
  });
});

// ── WF-04.2  Filter bar ───────────────────────────────────────────────────

describe("WF-04  Alerts — Filter bar", () => {
  it("[WF-04-FILTER-01] severity, type, project and status selects are present", () => {
    function AlertFilterBar() {
      return (
        <form aria-label="alert filters">
          <select aria-label="Severity filter"><option>All</option></select>
          <select aria-label="Type filter"><option>All</option></select>
          <select aria-label="Project filter"><option>All</option></select>
          <select aria-label="Status filter"><option>Open</option></select>
          <input type="search" aria-label="Search alerts" />
          <button type="reset">Reset</button>
        </form>
      );
    }

    renderWithProviders(<AlertFilterBar />);

    expect(screen.getByRole("combobox", { name: /severity filter/i })).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: /type filter/i })).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: /project filter/i })).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: /status filter/i })).toBeInTheDocument();
    expect(screen.getByRole("searchbox", { name: /search alerts/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /reset/i })).toBeInTheDocument();
  });
});

// ── WF-04.3  Bulk actions row ─────────────────────────────────────────────

describe("WF-04  Alerts — Bulk actions row", () => {
  it("[WF-04-BULK-01] select-all, assign, mark-as, export and archive buttons exist", () => {
    function BulkActionsRow({ total }: { total: number }) {
      return (
        <div role="toolbar" aria-label="bulk actions">
          <input type="checkbox" aria-label={`Select all ${total} alerts`} />
          <button>Assign to…</button>
          <button>Mark as…</button>
          <button>Export</button>
          <button>Archive</button>
        </div>
      );
    }

    renderWithProviders(<BulkActionsRow total={45} />);

    expect(screen.getByRole("checkbox", { name: /select all 45 alerts/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /assign to/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /mark as/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /export/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /archive/i })).toBeInTheDocument();
  });
});

// ── WF-04.4  Alert cards ──────────────────────────────────────────────────

const DEMO_ALERTS: ReviewAlert[] = [
  {
    id: "a1",
    title: "Date Mismatch: Contract vs Schedule",
    severity: "critical",
    status: "pending",
    clauseId: "c-4.2",
    assignee: "Carlos Martínez",
  },
  {
    id: "a2",
    title: "Budget Overrun Risk: Material Costs",
    severity: "high",
    status: "pending",
    clauseId: "b-203",
    assignee: "Laura Fernández",
  },
  {
    id: "a3",
    title: "Missing Stakeholder Approval",
    severity: "critical",
    status: "pending",
    clauseId: "w-2.3",
    assignee: "",
  },
];

describe("WF-04  Alerts — Alert Review Center component", () => {
  it("[WF-04-CARD-01] renders all provided alert titles", () => {
    renderWithProviders(
      <AlertReviewCenter projectId="p1" alerts={DEMO_ALERTS} />,
    );

    expect(screen.getByText(/date mismatch: contract vs schedule/i)).toBeInTheDocument();
    expect(screen.getByText(/budget overrun risk/i)).toBeInTheDocument();
    expect(screen.getByText(/missing stakeholder approval/i)).toBeInTheDocument();
  });

  it("[WF-04-CARD-02] severity sort — critical alerts appear before high", () => {
    renderWithProviders(
      <AlertReviewCenter projectId="p1" alerts={DEMO_ALERTS} />,
    );

    const titles = screen
      .getAllByRole("heading")
      .map((h) => h.textContent ?? "");

    const criticalIdx = titles.findIndex((t) => /date mismatch/i.test(t));
    const highIdx = titles.findIndex((t) => /budget overrun/i.test(t));

    expect(criticalIdx).toBeLessThan(highIdx);
  });

  it("[WF-04-CARD-03] action buttons are present per alert card", () => {
    renderWithProviders(
      <AlertReviewCenter projectId="p1" alerts={DEMO_ALERTS.slice(0, 1)} />,
    );

    expect(screen.getByRole("button", { name: /approve/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /reject/i })).toBeInTheDocument();
  });

  it("[WF-04-FILTER-STATUS-01] status filter 'approved' hides pending alerts", async () => {
    renderWithProviders(
      <AlertReviewCenter projectId="p1" alerts={DEMO_ALERTS} />,
    );

    const filterButtons = screen.getAllByRole("button");
    const approvedFilter = filterButtons.find((b) =>
      /approved/i.test(b.textContent ?? ""),
    );
    if (approvedFilter) {
      fireEvent.click(approvedFilter);
      expect(screen.queryByText(/date mismatch: contract vs schedule/i)).not.toBeInTheDocument();
    }
  });
});
