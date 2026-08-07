/**
 * Test Suite ID: TASK-1423
 * Route Coverage: canonical WBS route parity
 */
import { describe, expect, it, vi } from "vitest";
import { renderWithProviders, screen } from "@/src/tests/test-utils";
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
