/**
 * Test Suite ID: TASK-1423
 * Route Coverage: canonical WBS route parity
 */
import { describe, expect, it } from "vitest";
import { renderWithProviders, screen } from "@/src/tests/test-utils";
import ProjectWBSPage from "./page";

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
