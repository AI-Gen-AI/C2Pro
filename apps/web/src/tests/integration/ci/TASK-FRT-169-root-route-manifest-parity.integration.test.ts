/**
 * Test Suite ID: TASK-FRT-169
 * Purpose: Prevent duplicate root routes that break Vercel client-reference manifest lookup.
 */

import { describe, expect, it } from "vitest";
import { existsSync } from "node:fs";
import { resolve } from "node:path";

describe("TASK-FRT-169 root route manifest parity", () => {
  it("keeps the root pathname owned by app/page.tsx only", () => {
    const appRootPage = resolve(process.cwd(), "app", "page.tsx");
    const groupedRootPage = resolve(process.cwd(), "app", "(app)", "page.tsx");

    expect(existsSync(appRootPage)).toBe(true);
    expect(existsSync(groupedRootPage)).toBe(false);
  });
});
