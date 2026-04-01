/**
 * Test Suite ID: TASK-1423
 * Route Coverage: canonical budget route parity
 */
import { describe, expect, it } from "vitest";
import { renderWithProviders, screen } from "@/src/tests/test-utils";
import ProjectBudgetPage from "./page";

describe("ProjectBudgetPage", () => {
  it("renders the canonical budget route with the legacy parity view", () => {
    renderWithProviders(<ProjectBudgetPage />);

    expect(screen.getByTestId("budget-page")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /budget overview/i }),
    ).toBeInTheDocument();
    expect(screen.getByTestId("budget-chart")).toBeInTheDocument();
  });
});
