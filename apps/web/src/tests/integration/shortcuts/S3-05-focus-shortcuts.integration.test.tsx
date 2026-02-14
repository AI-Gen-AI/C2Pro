/**
 * Test Suite ID: S3-05
 * Roadmap Reference: S3-05 Focus-scoped keyboard shortcuts (WCAG 2.1.4)
 */
import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@/src/tests/test-utils";
import { ShortcutScopeHarness } from "@/src/components/features/shortcuts/ShortcutScopeHarness";

describe("S3-05 RED - focus-scoped shortcuts integration", () => {
  it("[S3-05-RED-INT-01] evidence j/k works only while evidence region owns focus", () => {
    render(<ShortcutScopeHarness />);

    const evidence = screen.getByTestId("shortcut-scope-evidence");
    const alerts = screen.getByTestId("shortcut-scope-alerts");

    alerts.focus();
    fireEvent.keyDown(window, { key: "j" });
    expect(screen.getByTestId("shortcut-evidence-cursor")).toHaveTextContent("0");

    evidence.focus();
    fireEvent.keyDown(window, { key: "j" });
    expect(screen.getByTestId("shortcut-evidence-cursor")).toHaveTextContent("1");
  });

  it("[S3-05-RED-INT-02] alerts approve/reject shortcuts only work in alerts scope", () => {
    render(<ShortcutScopeHarness />);

    screen.getByTestId("shortcut-scope-evidence").focus();
    fireEvent.keyDown(window, { key: "a" });
    expect(screen.getByTestId("shortcut-alert-status")).toHaveTextContent("pending");

    screen.getByTestId("shortcut-scope-alerts").focus();
    fireEvent.keyDown(window, { key: "a" });
    expect(screen.getByTestId("shortcut-alert-status")).toHaveTextContent("approved");
  });

  it("[S3-05-RED-INT-03] question-mark help opens globally but is suppressed in text entry", () => {
    render(<ShortcutScopeHarness />);

    fireEvent.keyDown(window, { key: "?" });
    expect(screen.getByRole("dialog", { name: /keyboard shortcuts/i })).toBeInTheDocument();

    const input = screen.getByLabelText(/notes/i);
    input.focus();
    fireEvent.keyDown(input, { key: "?" });
    expect(screen.getAllByRole("dialog", { name: /keyboard shortcuts/i })).toHaveLength(1);
  });

  it("[S3-05-RED-INT-04] shortcut preferences persist via sessionStorage after remount", () => {
    sessionStorage.setItem(
      "s3-05-shortcut-prefs",
      JSON.stringify({ disabled: true, remap: { j: "n" } }),
    );

    const { unmount } = render(<ShortcutScopeHarness />);
    unmount();
    render(<ShortcutScopeHarness />);

    screen.getByTestId("shortcut-scope-evidence").focus();
    fireEvent.keyDown(window, { key: "j" });
    fireEvent.keyDown(window, { key: "n" });
    expect(screen.getByTestId("shortcut-evidence-cursor")).toHaveTextContent("0");
  });
});
