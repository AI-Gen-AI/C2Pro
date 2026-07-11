/**
 * Test for CategoryStatusBadge — ADR-009 §4.3 (color contract).
 *
 * Critical invariant: red is RESERVED for `conflicting_evidence` only.
 * Missing evidence renders amber/blue, never red.
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { CategoryStatusBadge } from "./CategoryStatusBadge";

describe("CategoryStatusBadge", () => {
  it("renders the 'scored' state in success green", () => {
    render(<CategoryStatusBadge status="scored" />);
    const badge = screen.getByTestId("status-badge-success");
    expect(badge).toHaveAttribute("data-status", "scored");
    expect(badge.className).toMatch(/emerald/);
  });

  it("renders red ONLY for conflicting_evidence", () => {
    render(<CategoryStatusBadge status="conflicting_evidence" />);
    const badge = screen.getByTestId("status-badge-destructive");
    expect(badge).toHaveAttribute("data-status", "conflicting_evidence");
    expect(badge.className).toMatch(/red/);
  });

  it("renders neutral gray for insufficient_evidence (NOT red)", () => {
    render(<CategoryStatusBadge status="insufficient_evidence" />);
    const badge = screen.getByTestId("status-badge-neutral");
    expect(badge.className).toMatch(/gray/);
    expect(badge.className).not.toMatch(/red-1|red-9/);
  });

  it("renders info blue for pending_documents", () => {
    render(<CategoryStatusBadge status="pending_documents" />);
    const badge = screen.getByTestId("status-badge-info");
    expect(badge.className).toMatch(/blue/);
    expect(badge.className).not.toMatch(/red-1|red-9/);
  });

  it("renders neutral gray for not_applicable", () => {
    render(<CategoryStatusBadge status="not_applicable" />);
    const badge = screen.getByTestId("status-badge-not-applicable");
    expect(badge.className).toMatch(/gray/);
  });

  it("renders amber-orange for processing_error", () => {
    render(<CategoryStatusBadge status="processing_error" />);
    expect(screen.getByTestId("status-badge-error")).toBeInTheDocument();
  });
});
