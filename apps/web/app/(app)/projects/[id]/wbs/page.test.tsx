/**
 * Test Suite ID: TASK-1423
 * Route Coverage: canonical WBS route parity
 * IR-4: the page renders the authoritative (procurement) WBS read-only; it offers no
 * create/edit/move actions because no served endpoint persists them.
 */
import { describe, expect, it, vi } from "vitest";
import { fireEvent, renderWithProviders, screen } from "@/src/tests/test-utils";
import type { WBSTreeItem } from "@/hooks/useWBSTree";
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
  hookState: { items: [] as WBSTreeItem[], expanded: new Set<string>(), totalItems: 0 as number | null },
}));

vi.mock("@/hooks/useWBSTree", () => ({
  useWBSTree: () => ({
    items: hookState.items,
    totalItems: hookState.totalItems,
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
  it("renders the canonical WBS route", () => {
    hookState.items = [];
    hookState.totalItems = 0;
    renderWithProviders(<ProjectWBSPage />);

    expect(screen.getByTestId("wbs-tree-view")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /work breakdown structure/i }),
    ).toBeInTheDocument();
    expect(screen.getByTestId("wbs-tree")).toBeInTheDocument();
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
});
