/**
 * Test Suite ID: S3-06
 * Roadmap Reference: S3-06 Alert undo + double invalidation
 */
import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@/src/tests/test-utils";
import { AlertUndoToast } from "@/src/components/features/alerts/AlertUndoToast";

describe("S3-06 RED - AlertUndoToast", () => {
  it("[S3-06-RED-UNIT-05] exposes status role and keyboard-activatable undo action", () => {
    let triggered = 0;
    render(
      <AlertUndoToast
        message="Alert approved"
        onUndo={() => {
          triggered += 1;
        }}
      />,
    );

    const status = screen.getByRole("status");
    expect(status).toHaveTextContent(/alert approved/i);

    const button = screen.getByRole("button", { name: /undo/i });
    button.focus();
    fireEvent.keyDown(button, { key: "Enter" });

    expect(triggered).toBe(1);
  });
});
