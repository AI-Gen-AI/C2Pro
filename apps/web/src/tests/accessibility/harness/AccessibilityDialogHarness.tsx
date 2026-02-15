/**
 * Test Suite ID: S3-12
 * Roadmap Reference: S3-12 A11y audit pass 1 + responsive pass (tablet)
 */
"use client";

import { useState } from "react";

export function AccessibilityDialogHarness() {
  const [open, setOpen] = useState(false);

  return (
    <>
      <button type="button" onClick={() => setOpen(true)}>
        Open modal
      </button>
      {open ? (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Sample dialog"
          onKeyDown={(event) => {
            if (event.key === "Escape") {
              setOpen(false);
              const trigger = document.querySelector<HTMLButtonElement>("button");
              trigger?.focus();
            }
          }}
        >
          Modal content
        </div>
      ) : null}
    </>
  );
}
