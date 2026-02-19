/**
 * Test Suite ID: S3-05
 * Roadmap Reference: S3-05 Focus-scoped keyboard shortcuts (WCAG 2.1.4)
 */
import { describe, expect, it } from "vitest";
import { render, screen } from "@/src/tests/test-utils";
import { ShortcutHelpDialog } from "@/components/features/shortcuts/ShortcutHelpDialog";

describe("S3-05 RED - ShortcutHelpDialog", () => {
  it("[S3-05-RED-UNIT-04] shows only active-scope shortcuts and hides inactive scope bindings", () => {
    render(
      <ShortcutHelpDialog
        open
        activeScopes={["evidence"]}
        bindings={{
          evidence: [
            { key: "j", label: "Next highlight" },
            { key: "k", label: "Previous highlight" },
          ],
          alerts: [{ key: "a", label: "Approve selected alert" }],
        }}
      />,
    );

    expect(screen.getByRole("dialog", { name: /keyboard shortcuts/i })).toBeInTheDocument();
    expect(screen.getByText(/next highlight/i)).toBeInTheDocument();
    expect(screen.getByText(/previous highlight/i)).toBeInTheDocument();
    expect(screen.queryByText(/approve selected alert/i)).not.toBeInTheDocument();
  });
});
