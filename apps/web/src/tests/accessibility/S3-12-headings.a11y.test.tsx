/**
 * Test Suite ID: S3-12
 * Roadmap Reference: S3-12 A11y audit pass 1 + responsive pass (tablet)
 */
import { describe, expect, it } from "vitest";
import { render, screen } from "@/src/tests/test-utils";
import { AccessibilityHeadingsHarness } from "@/src/tests/accessibility/harness/AccessibilityHeadingsHarness";

describe("S3-12 RED - headings", () => {
  it("[S3-12-RED-UNIT-02] enforces valid heading hierarchy without skips", () => {
    render(<AccessibilityHeadingsHarness />);

    const headings = screen.getAllByRole("heading");
    const levels = headings.map((heading) => Number(heading.tagName.slice(1)));
    expect(levels).toEqual([1, 2, 3]);
  });
});
