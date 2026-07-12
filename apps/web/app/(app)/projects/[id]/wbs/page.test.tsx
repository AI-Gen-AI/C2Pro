/**
 * Test Suite ID: TASK-1423
 * Route Coverage: canonical WBS route parity
 */
import { describe, expect, it, vi } from "vitest";
import { renderWithProviders, screen } from "@/src/tests/test-utils";
import ProjectWBSPage from "./page";

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "proj-real-wbs" }),
}));

vi.mock("@/hooks/useWBSTree", () => ({
  useWBSTree: () => ({
    items: [],
    isLoading: false,
    isError: false,
    error: null,
    updateItem: vi.fn(),
    createItem: vi.fn(),
    deleteItem: vi.fn(),
    moveItem: vi.fn(),
    expandedItems: new Set<string>(),
    toggleExpanded: vi.fn(),
    expandAll: vi.fn(),
    collapseAll: vi.fn(),
  }),
}));

describe("ProjectWBSPage", () => {
  it("renders the canonical WBS route with the legacy parity view", () => {
    renderWithProviders(<ProjectWBSPage />);

    expect(screen.getByTestId("wbs-tree-view")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /work breakdown structure/i }),
    ).toBeInTheDocument();
    expect(screen.getByTestId("wbs-tree")).toBeInTheDocument();
  });
});
