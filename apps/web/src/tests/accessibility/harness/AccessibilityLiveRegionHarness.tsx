/**
 * Test Suite ID: S3-12
 * Roadmap Reference: S3-12 A11y audit pass 1 + responsive pass (tablet)
 */
"use client";

import { useState } from "react";

export function AccessibilityLiveRegionHarness() {
  const [message, setMessage] = useState("idle");
  const [count, setCount] = useState(0);

  return (
    <>
      <button
        type="button"
        onClick={() => {
          setMessage("processing started");
          setCount((value) => value + 1);
        }}
      >
        Start processing
      </button>
      <div role="status">{message}</div>
      <div data-testid="live-announcement-count">{count}</div>
    </>
  );
}
