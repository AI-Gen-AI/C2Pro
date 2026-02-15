/**
 * Test Suite ID: S3-12
 * Roadmap Reference: S3-12 A11y audit pass 1 + responsive pass (tablet)
 */
import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@/src/tests/test-utils";
import { AccessibilityDialogHarness } from "@/src/tests/accessibility/harness/AccessibilityDialogHarness";

describe("S3-12 RED - dialog focus", () => {
  it("[S3-12-RED-UNIT-05] traps focus and returns trigger focus on close", () => {
    render(<AccessibilityDialogHarness />);

    const trigger = screen.getByRole("button", { name: /open modal/i });
    fireEvent.click(trigger);
    expect(screen.getByRole("dialog", { name: /sample dialog/i })).toBeInTheDocument();

    fireEvent.keyDown(screen.getByRole("dialog", { name: /sample dialog/i }), { key: "Escape" });
    expect(trigger).toHaveFocus();
  });
});
