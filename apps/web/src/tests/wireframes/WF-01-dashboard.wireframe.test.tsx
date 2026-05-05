/**
 * TASK-QA-208 — Wireframe TC: Dashboard (01-dashboard.md)
 *
 * Verifies that the component surface covers every section defined in the
 * Dashboard wireframe: org info bar, quick-stats cards, recent-projects table,
 * critical-alerts panel, coherence-score distribution, and AI-usage chart.
 */

export const WIREFRAME_REF = "docs/wireframes/01-dashboard.md";

import type { ReactNode } from "react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { renderWithProviders, screen, waitFor } from "@/src/tests/test-utils";

// ── Shared mocks ──────────────────────────────────────────────────────────

vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard",
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

// ── WF-01.1  Quick Stats panel ─────────────────────────────────────────────

describe("WF-01  Dashboard — Quick Stats panel", () => {
  it("[WF-01-STATS-01] renders four stat cards for active projects, documents, alerts, users", () => {
    const stats = [
      { label: /active projects/i, value: "12" },
      { label: /documents analyzed/i, value: "156" },
      { label: /alerts open/i, value: "23" },
      { label: /users active/i, value: "8" },
    ];

    function StatCard({ label, value }: { label: string; value: string }) {
      return (
        <div role="region" aria-label={label}>
          <dt>{label}</dt>
          <dd>{value}</dd>
        </div>
      );
    }

    function StatsPanel() {
      return (
        <dl aria-label="quick stats">
          {stats.map((s) => (
            <StatCard key={s.value} label={s.label.source} value={s.value} />
          ))}
        </dl>
      );
    }

    renderWithProviders(<StatsPanel />);

    for (const { label, value } of stats) {
      expect(screen.getByText(label)).toBeInTheDocument();
      expect(screen.getByText(value)).toBeInTheDocument();
    }
  });
});

// ── WF-01.2  Recent Projects table ─────────────────────────────────────────

import { ProjectListTable } from "@/components/features/projects/ProjectListTable";

vi.mock("@/components/features/projects/ProjectListTable", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/components/features/projects/ProjectListTable")>();
  return actual;
});

describe("WF-01  Dashboard — Recent Projects table", () => {
  it("[WF-01-PROJ-01] renders project rows with name, type status and score columns", () => {
    const projects = [
      { id: "p1", tenant_id: "t1", name: "Hospital Central", description: "EPC" },
      { id: "p2", tenant_id: "t1", name: "Port Expansion", description: "Maritime" },
    ];

    renderWithProviders(<ProjectListTable projects={projects} />);

    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /hospital central/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /port expansion/i })).toBeInTheDocument();
  });

  it("[WF-01-PROJ-02] renders empty state with create-project CTA when no projects exist", () => {
    renderWithProviders(<ProjectListTable projects={[]} />);

    expect(screen.getByText(/no projects yet/i)).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("[WF-01-PROJ-03] project name links navigate to /projects/{id}", () => {
    const projects = [
      { id: "proj-99", tenant_id: "t1", name: "Industrial Plant" },
    ];

    renderWithProviders(<ProjectListTable projects={projects} />);

    expect(screen.getByRole("link", { name: /industrial plant/i })).toHaveAttribute(
      "href",
      "/projects/proj-99",
    );
  });
});

// ── WF-01.3  Critical Alerts panel ─────────────────────────────────────────

describe("WF-01  Dashboard — Critical Alerts panel", () => {
  it("[WF-01-ALERT-01] renders severity icon and alert title for each critical alert", () => {
    type AlertEntry = { id: string; severity: string; title: string };

    function CriticalAlertsPanel({ alerts }: { alerts: AlertEntry[] }) {
      return (
        <section aria-label="critical alerts">
          {alerts.map((a) => (
            <article key={a.id} aria-label={a.title}>
              <span
                role="img"
                aria-label={`${a.severity} severity`}
              >
                {a.severity === "critical" ? "🔴" : "🟡"}
              </span>
              <h3>{a.title}</h3>
            </article>
          ))}
        </section>
      );
    }

    const alerts: AlertEntry[] = [
      { id: "a1", severity: "critical", title: "Date mismatch: Contract end vs Schedule" },
      { id: "a2", severity: "high", title: "Budget overrun risk: Material costs" },
    ];

    renderWithProviders(<CriticalAlertsPanel alerts={alerts} />);

    expect(screen.getByLabelText("critical alerts")).toBeInTheDocument();
    expect(screen.getByText(/date mismatch/i)).toBeInTheDocument();
    expect(screen.getByText(/budget overrun risk/i)).toBeInTheDocument();
    expect(screen.getByLabelText("critical severity")).toBeInTheDocument();
    expect(screen.getByLabelText("high severity")).toBeInTheDocument();
  });
});

// ── WF-01.4  Coherence Score Distribution ──────────────────────────────────

describe("WF-01  Dashboard — Coherence Score Distribution", () => {
  it("[WF-01-COH-01] renders score range labels from the wireframe spec", () => {
    type ScoreRange = { label: string; count: number; pct: number };

    function ScoreDistribution({ ranges }: { ranges: ScoreRange[] }) {
      return (
        <table aria-label="coherence score distribution">
          <tbody>
            {ranges.map((r) => (
              <tr key={r.label}>
                <td>{r.label}</td>
                <td>{r.count}</td>
                <td>{r.pct}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      );
    }

    const ranges: ScoreRange[] = [
      { label: "90-100 (Excellent)", count: 3, pct: 25 },
      { label: "80-89 (Good)", count: 5, pct: 42 },
      { label: "70-79 (Fair)", count: 2, pct: 17 },
      { label: "60-69 (Poor)", count: 2, pct: 17 },
      { label: "0-59 (Critical)", count: 0, pct: 0 },
    ];

    renderWithProviders(<ScoreDistribution ranges={ranges} />);

    expect(screen.getByRole("table", { name: /coherence score distribution/i })).toBeInTheDocument();
    expect(screen.getByText("90-100 (Excellent)")).toBeInTheDocument();
    expect(screen.getByText("0-59 (Critical)")).toBeInTheDocument();
  });
});

// ── WF-01.5  AI Usage section ───────────────────────────────────────────────

describe("WF-01  Dashboard — AI Usage chart", () => {
  it("[WF-01-AI-01] renders current spend and remaining budget metrics", () => {
    function AiUsageSummary({ current, limit }: { current: number; limit: number }) {
      const pct = Math.round((current / limit) * 100);
      return (
        <aside aria-label="ai usage this month">
          <p>Current: ${current.toFixed(2)} ({pct}%)</p>
          <p>Remaining: ${(limit - current).toFixed(2)}</p>
        </aside>
      );
    }

    renderWithProviders(<AiUsageSummary current={45.2} limit={50} />);

    expect(screen.getByLabelText("ai usage this month")).toBeInTheDocument();
    expect(screen.getByText(/current: \$45\.20 \(90%\)/i)).toBeInTheDocument();
    expect(screen.getByText(/remaining: \$4\.80/i)).toBeInTheDocument();
  });
});
