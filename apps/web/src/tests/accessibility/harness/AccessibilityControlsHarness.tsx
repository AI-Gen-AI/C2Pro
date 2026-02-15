/**
 * Test Suite ID: S3-12
 * Roadmap Reference: S3-12 A11y audit pass 1 + responsive pass (tablet)
 */
"use client";

export function AccessibilityControlsHarness() {
  return (
    <button
      type="button"
      data-focus-visible="true"
      aria-label="Approve alert"
    >
      Approve alert
    </button>
  );
}
