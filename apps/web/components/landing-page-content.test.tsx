/**
 * Test Suite ID: TASK-1429
 * Backlog Task: TASK-1429
 */
import { describe, expect, it } from "vitest";
import { within } from "@/src/tests/test-utils";
import { render, screen } from "@/src/tests/test-utils";
import LandingPageContent from "./landing-page-content";

describe("LandingPageContent", () => {
  it("[TASK-1429-ROUTE-01] points public demo entry actions at a real public demo route", () => {
    render(<LandingPageContent />);

    expect(screen.getByRole("link", { name: /view live demo/i })).toHaveAttribute(
      "href",
      "/demo/documents",
    );
    expect(screen.getByRole("link", { name: /try demo first/i })).toHaveAttribute(
      "href",
      "/demo/documents",
    );
  });

  it("[TASK-1429-ROUTE-02] renders CTA links without nesting button elements inside anchor elements", () => {
    render(<LandingPageContent />);

    for (const name of [
      /access real workspace/i,
      /view live demo/i,
      /go to real platform/i,
      /try demo first/i,
    ]) {
      const link = screen.getByRole("link", { name });
      expect(within(link).queryByRole("button")).not.toBeInTheDocument();
    }
  });
});
