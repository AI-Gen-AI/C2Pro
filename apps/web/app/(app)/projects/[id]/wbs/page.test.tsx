/**
 * Test Suite ID: TASK-1423
 * Route Coverage: canonical WBS route parity
 * IR-4: the page renders the authoritative (procurement) WBS read-only; it offers no
 * create/edit/move actions because no served endpoint persists them.
 *
 * PC-7a (#672/#688): the page must show the real WBS authority state from the single
 * resolver (NO_WBS / DRAFT_ONLY / LEGACY_UNGOVERNED / APPROVED_BASELINE) and coverage,
 * and must never present WBS dates/budget as approved schedule/cost authority.
 *
 * PC-7b (#672, board #1049): the page must show a real alert count/panel and must
 * never imply 0/known alerts before the fetch actually resolves, and must never link
 * a clause that was not actually persisted as addressable evidence.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, renderWithProviders, screen } from "@/src/tests/test-utils";
import type { WBSTreeItem } from "@/hooks/useWBSTree";
import type { ReviewAlert } from "@/components/features/alerts/AlertReviewCenter";
import type {
  ProjectWBSAuthority,
  ProjectWBSCoverage,
} from "@/lib/api/generated/models";
import ProjectWBSPage from "./page";

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "proj-real-wbs" }),
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
}));

vi.mock("@/config/env", () => ({
  env: {
    FEATURE_PHASE2_MODULES: true,
    FEATURE_INTERNAL_DASHBOARDS: false,
    FEATURE_RACI_GENERATION: false,
    IS_DEMO: false,
    IS_DEV: false,
    APP_MODE: "production",
    API_BASE_URL: "/api",
    BACKEND_ORIGIN: "",
    COHERENCE_BASE_URL: "/coherence",
    SENTRY_DSN: undefined,
  },
}));

const { hookState } = vi.hoisted(() => ({
  hookState: {
    items: [] as WBSTreeItem[],
    expanded: new Set<string>(),
    totalItems: 0 as number | null,
    coverage: null as ProjectWBSCoverage | null,
    authority: null as ProjectWBSAuthority | null,
  },
}));

vi.mock("@/hooks/useWBSTree", () => ({
  useWBSTree: () => ({
    items: hookState.items,
    totalItems: hookState.totalItems,
    coverage: hookState.coverage,
    authority: hookState.authority,
    isLoading: false,
    isError: false,
    error: null,
    expandedItems: hookState.expanded,
    toggleExpanded: (id: string) => {
      if (hookState.expanded.has(id)) hookState.expanded.delete(id);
      else hookState.expanded.add(id);
    },
    expandAll: vi.fn(),
    collapseAll: vi.fn(),
    refetch: vi.fn(),
  }),
}));

const { alertsState } = vi.hoisted(() => ({
  alertsState: {
    alerts: [] as ReviewAlert[],
    loading: false,
    error: null as Error | null,
  },
}));

vi.mock("@/components/features/wbs/TechnicalWBSReviewPanel", () => ({
  TechnicalWBSReviewPanel: () => <div data-testid="technical-wbs-review-mock" />,
}));
vi.mock("@/components/features/wbs/CanonicalTechnicalWBSLinksPanel", () => ({
  CanonicalTechnicalWBSLinksPanel: () => <div data-testid="technical-wbs-approved-mock" />,
}));

vi.mock("@/hooks/useProjectAlerts", () => ({
  useProjectAlerts: () => ({
    alerts: alertsState.alerts,
    loading: alertsState.loading,
    error: alertsState.error,
    refetch: vi.fn(),
  }),
}));

function authority(overrides: Partial<ProjectWBSAuthority>): ProjectWBSAuthority {
  return {
    state: "LEGACY_UNGOVERNED",
    display_state: "LEGACY_UNGOVERNED",
    approved: false,
    scope_label: "Unapproved / Legacy WBS",
    baseline_id: null,
    baseline_no: null,
    tree_digest: null,
    applied_at: null,
    draft_exists: false,
    dates_schedule_authority: false,
    budget_cost_authority: false,
    ...overrides,
  };
}

const child: WBSTreeItem = {
  id: "child",
  code: "1.1",
  name: "Quay wall",
  level: 2,
  itemType: "work_package",
  plannedStart: "2026-10-01T00:00:00+00:00",
  plannedEnd: "2027-06-30T00:00:00+00:00",
  children: [],
};
const root: WBSTreeItem = {
  id: "root",
  code: "1",
  name: "Harbour Extension",
  level: 1,
  itemType: "deliverable",
  children: [child],
};

describe("ProjectWBSPage", () => {
  beforeEach(() => {
    hookState.coverage = null;
    hookState.authority = null;
    alertsState.alerts = [];
    alertsState.loading = false;
    alertsState.error = null;
  });

  it("renders the canonical WBS route", () => {
    hookState.items = [];
    hookState.totalItems = 0;
    renderWithProviders(<ProjectWBSPage />);

    expect(screen.getByTestId("wbs-tree-view")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /work breakdown structure/i }),
    ).toBeInTheDocument();
    expect(screen.getByTestId("wbs-tree")).toBeInTheDocument();
    expect(screen.getByTestId("technical-wbs-approved-mock")).toBeInTheDocument();
    expect(screen.getByText(/no wbs items recorded for this project/i)).toBeInTheDocument();
  });

  it("is read-only: no add, edit or drag affordances and no invented progress", () => {
    hookState.items = [root];
    hookState.totalItems = 2;
    hookState.expanded = new Set(["root"]);
    renderWithProviders(<ProjectWBSPage />);

    expect(screen.queryByRole("button", { name: /add item/i })).not.toBeInTheDocument();
    expect(screen.queryByTestId("wbs-edit-root")).not.toBeInTheDocument();
    expect(screen.getByTestId("wbs-item-root")).not.toHaveAttribute("draggable", "true");
    expect(screen.queryByTestId("wbs-item-root-completion")).not.toBeInTheDocument();
    expect(screen.queryByText(/click "add item"/i)).not.toBeInTheDocument();
  });

  it("shows nested items with their type and planned window", () => {
    hookState.items = [root];
    hookState.totalItems = 2;
    hookState.expanded = new Set();
    const { rerender } = renderWithProviders(<ProjectWBSPage />);

    expect(screen.queryByText("Quay wall")).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId("wbs-expand-root"));
    rerender(<ProjectWBSPage />);

    expect(screen.getByText("Quay wall")).toBeInTheDocument();
    expect(screen.getByTestId("wbs-item-child")).toHaveTextContent("Work package");
    expect(screen.getByTestId("wbs-item-child-planned")).toHaveTextContent("2026-10-01 → 2027-06-30");
    expect(screen.getByTestId("wbs-item-root-planned")).toHaveTextContent("Not scheduled");
    expect(screen.getByText("2 items")).toBeInTheDocument();
  });

  it("renders no authority banner while authority has not loaded", () => {
    hookState.items = [];
    hookState.totalItems = 0;
    renderWithProviders(<ProjectWBSPage />);

    expect(screen.queryByTestId("wbs-authority-banner")).not.toBeInTheDocument();
  });

  it.each([
    ["NO_WBS", "No WBS"],
    ["DRAFT_ONLY", "Draft WBS (not approved)"],
    ["LEGACY_UNGOVERNED", "Unapproved / Legacy WBS"],
  ] as const)("shows the %s authority state honestly, without implying an approved baseline", (state, label) => {
    hookState.items = [];
    hookState.totalItems = 0;
    hookState.authority = authority({
      state: state === "DRAFT_ONLY" ? "NO_WBS" : state,
      display_state: state,
      scope_label: label,
      draft_exists: state === "DRAFT_ONLY",
    });
    renderWithProviders(<ProjectWBSPage />);

    const banner = screen.getByTestId("wbs-authority-banner");
    expect(banner).toHaveAttribute("data-authority-state", state);
    expect(screen.getByTestId("wbs-authority-label")).toHaveTextContent(label);
    expect(screen.queryByTestId("wbs-authority-applied-at")).not.toBeInTheDocument();
    // Never implied as approved cost/schedule authority outside APPROVED_BASELINE.
    expect(screen.getByTestId("wbs-authority-disclaimer")).toHaveTextContent(
      /not approved schedule or cost authority/i,
    );
  });

  it("shows APPROVED_BASELINE with its baseline number and approval date", () => {
    hookState.items = [root];
    hookState.totalItems = 2;
    hookState.authority = authority({
      state: "APPROVED_BASELINE",
      display_state: "APPROVED_BASELINE",
      approved: true,
      scope_label: "Approved WBS Baseline #3",
      baseline_id: "baseline-3",
      baseline_no: 3,
      applied_at: "2026-10-05T12:00:00+00:00",
    });
    renderWithProviders(<ProjectWBSPage />);

    expect(screen.getByTestId("wbs-authority-label")).toHaveTextContent(
      "Approved WBS Baseline #3",
    );
    expect(screen.getByTestId("wbs-authority-applied-at")).toHaveTextContent("2026-10-05");
    // Even an approved baseline confers no authority on dates/budget.
    expect(screen.getByTestId("wbs-authority-disclaimer")).toHaveTextContent(
      /not approved schedule or cost authority/i,
    );
  });

  it("flags an open WBS change set on top of an approved baseline, without claiming it is pending review", () => {
    // `draft_exists` is true for both an unsubmitted DRAFT and a SUBMITTED change set
    // (backend's `open_change_sets > 0`); an unsubmitted draft is NOT "pending review",
    // so the banner must not assert a review status the backend does not report.
    hookState.items = [root];
    hookState.totalItems = 2;
    hookState.authority = authority({
      state: "APPROVED_BASELINE",
      display_state: "APPROVED_BASELINE",
      approved: true,
      scope_label: "Approved WBS Baseline #3",
      draft_exists: true,
    });
    renderWithProviders(<ProjectWBSPage />);

    const flag = screen.getByTestId("wbs-authority-draft-pending");
    expect(flag).toBeInTheDocument();
    expect(flag).toHaveTextContent("Open WBS change set");
    expect(flag).not.toHaveTextContent(/pending review/i);
    expect(screen.queryByText(/pending review/i)).not.toBeInTheDocument();
  });

  it("renders coverage honestly, distinguishing approved scope from unapproved legacy items", () => {
    hookState.items = [root];
    hookState.totalItems = 2;
    hookState.coverage = {
      total_items: 4,
      items_with_budget: 2,
      items_with_dates: 1,
      items_with_alerts: 0,
      completion_average: 0,
      approved_scope_items: 0,
      unapproved_legacy_items: 4,
    };
    renderWithProviders(<ProjectWBSPage />);

    const summary = screen.getByTestId("wbs-coverage-summary");
    expect(summary).toHaveTextContent("4 items total");
    expect(summary).toHaveTextContent("2 with budget");
    expect(summary).toHaveTextContent("1 with dates");
    expect(summary).toHaveTextContent("4 unapproved legacy");
    expect(summary).not.toHaveTextContent("in the approved baseline");
  });

  it("renders no coverage summary while coverage has not loaded", () => {
    hookState.items = [];
    hookState.totalItems = 0;
    renderWithProviders(<ProjectWBSPage />);

    expect(screen.queryByTestId("wbs-coverage-summary")).not.toBeInTheDocument();
  });

  it("shows a loading state for alerts instead of implying a count before the fetch resolves", () => {
    hookState.items = [];
    hookState.totalItems = 0;
    alertsState.loading = true;
    renderWithProviders(<ProjectWBSPage />);

    expect(screen.getByText(/loading project alerts/i)).toBeInTheDocument();
    expect(screen.queryByTestId("wbs-alerts-count")).not.toBeInTheDocument();
  });

  it("shows an alert fetch failure honestly instead of a fabricated empty/zero state", () => {
    hookState.items = [];
    hookState.totalItems = 0;
    alertsState.error = new Error("alerts service unavailable");
    renderWithProviders(<ProjectWBSPage />);

    expect(screen.getByTestId("wbs-alerts-error")).toHaveTextContent(
      "alerts service unavailable",
    );
    expect(screen.queryByTestId("wbs-alerts-count")).not.toBeInTheDocument();
  });

  it("shows the real alert count and no-alerts message when none are recorded", () => {
    hookState.items = [];
    hookState.totalItems = 0;
    alertsState.alerts = [];
    renderWithProviders(<ProjectWBSPage />);

    expect(screen.getByTestId("wbs-alerts-count")).toHaveTextContent("0 alerts");
    expect(screen.getByText(/no alerts recorded for this project/i)).toBeInTheDocument();
  });

  it("links an alert's real, persisted source_clause_id to its evidence document", () => {
    hookState.items = [];
    hookState.totalItems = 0;
    alertsState.alerts = [
      {
        id: "alert-1",
        title: "Indemnity clause conflicts with schedule",
        severity: "high",
        status: "pending",
        clauseId: "clause-§5.2",
        addressableClauseId: "clause-§5.2",
        sourceDocumentId: "doc-42",
      },
    ];
    renderWithProviders(<ProjectWBSPage />);

    expect(screen.getByTestId("wbs-alerts-count")).toHaveTextContent("1 alert");
    const link = screen.getByTestId("wbs-alert-alert-1-evidence-link");
    expect(link).toHaveTextContent("clause-§5.2");
    expect(link).toHaveAttribute(
      "href",
      "/projects/proj-real-wbs/evidence?documentId=doc-42&highlightId=clause-%C2%A75.2",
    );
  });

  it("shows an unresolved detector clause id as plain text, never as a fabricated link", () => {
    hookState.items = [];
    hookState.totalItems = 0;
    alertsState.alerts = [
      {
        id: "alert-2",
        title: "Line item exceeds approved scope",
        severity: "critical",
        status: "pending",
        // Reported by the detector but not yet persisted as addressable evidence.
        clauseId: "clause-§3.1",
      },
    ];
    renderWithProviders(<ProjectWBSPage />);

    expect(screen.getByTestId("wbs-alert-alert-2-clause")).toHaveTextContent("clause-§3.1");
    expect(screen.queryByTestId("wbs-alert-alert-2-evidence-link")).not.toBeInTheDocument();
  });
});
