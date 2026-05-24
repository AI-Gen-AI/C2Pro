/**
 * Test for CoherenceEmptyState — ADR-009 §18.
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { CoherenceEmptyState } from "./CoherenceEmptyState";

describe("CoherenceEmptyState", () => {
  it("renders the 'Pending evidence' heading", () => {
    render(<CoherenceEmptyState projectId="proj-1" reason={null} />);
    expect(
      screen.getByRole("heading", { name: /pending evidence/i }),
    ).toBeInTheDocument();
  });

  it("renders the upload CTA pointing at the project documents", () => {
    render(<CoherenceEmptyState projectId="proj-42" reason={null} />);
    const cta = screen.getByTestId("empty-state-cta");
    expect(cta).toBeInTheDocument();
    expect(cta).toHaveAttribute("href", "/projects/proj-42/documents");
  });

  it("displays the reason literal when provided", () => {
    render(
      <CoherenceEmptyState
        projectId="proj-1"
        reason="insufficient_active_weight"
      />,
    );
    expect(screen.getByTestId("empty-state-reason")).toHaveTextContent(
      "insufficient_active_weight",
    );
  });

  it("never renders the text '0' as a fallback score", () => {
    const { container } = render(
      <CoherenceEmptyState projectId="proj-1" reason="pending_documents" />,
    );
    // Must not contain bare 0/100 fallback that the old DashboardClient produced
    expect(container.textContent).not.toMatch(/\b0\s*\/\s*100\b/);
    expect(container.textContent).not.toMatch(/^0$/);
  });
});
