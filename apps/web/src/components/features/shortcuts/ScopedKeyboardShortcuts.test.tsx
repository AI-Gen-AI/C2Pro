/**
 * Test Suite ID: S3-05
 * Roadmap Reference: S3-05 Focus-scoped keyboard shortcuts (WCAG 2.1.4)
 */
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@/src/tests/test-utils";
import { ScopedKeyboardShortcuts } from "@/src/components/features/shortcuts/ScopedKeyboardShortcuts";

describe("S3-05 RED - ScopedKeyboardShortcuts", () => {
  it("[S3-05-RED-UNIT-01] executes shortcuts only when owning scope is active", () => {
    const onNext = vi.fn();

    render(
      <ScopedKeyboardShortcuts
        scopeId="evidence"
        isScopeActive={false}
        bindings={{ j: onNext }}
      />,
    );

    fireEvent.keyDown(window, { key: "j" });
    expect(onNext).not.toHaveBeenCalled();
  });

  it("[S3-05-RED-UNIT-02] suppresses character shortcuts while typing in editable fields", () => {
    const onNext = vi.fn();

    render(
      <>
        <ScopedKeyboardShortcuts
          scopeId="evidence"
          isScopeActive
          bindings={{ j: onNext }}
        />
        <input aria-label="Notes" />
      </>,
    );

    const input = screen.getByLabelText(/notes/i);
    input.focus();
    fireEvent.keyDown(input, { key: "j" });

    expect(onNext).not.toHaveBeenCalled();
  });

  it("[S3-05-RED-UNIT-03] supports disable/remap for single-character bindings", () => {
    const onNext = vi.fn();

    render(
      <ScopedKeyboardShortcuts
        scopeId="evidence"
        isScopeActive
        bindings={{ j: onNext }}
        preferences={{ disabled: true, remap: { j: "n" } }}
      />,
    );

    fireEvent.keyDown(window, { key: "j" });
    fireEvent.keyDown(window, { key: "n" });
    expect(onNext).toHaveBeenCalledTimes(0);
  });

  it("[S3-05-RED-UNIT-05] removes listeners on unmount to avoid cross-page leakage", () => {
    const onNext = vi.fn();

    const { unmount } = render(
      <ScopedKeyboardShortcuts
        scopeId="evidence"
        isScopeActive
        bindings={{ j: onNext }}
      />,
    );

    unmount();
    fireEvent.keyDown(window, { key: "j" });
    expect(onNext).not.toHaveBeenCalled();
  });

  it("[S3-05-RED-UNIT-06] ignores reserved system/browser shortcuts", () => {
    const onRefreshAction = vi.fn();

    render(
      <ScopedKeyboardShortcuts
        scopeId="evidence"
        isScopeActive
        bindings={{ r: onRefreshAction }}
      />,
    );

    fireEvent.keyDown(window, { key: "r", ctrlKey: true });
    fireEvent.keyDown(window, { key: "l", metaKey: true });

    expect(onRefreshAction).not.toHaveBeenCalled();
  });
});
