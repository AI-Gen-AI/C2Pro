/**
 * Test Suite ID: TASK-1425 (superseded by TASK-FRT-183)
 * Route Coverage: /dashboard is a real authenticated route inside the (app) shell.
 *
 * History: TASK-1425 retired the legacy app/dashboard tree and redirected
 * /dashboard to /. EPIC-FRT-LANDING-SYNC later made / a static public landing,
 * and TASK-FRT-183 re-established /dashboard as the authenticated home — the
 * old redirects would bounce signed-in users to the marketing page, so they
 * must never come back.
 */
import { describe, expect, it } from "vitest";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

describe("TASK-1425/TASK-FRT-183 dashboard routing", () => {
  it("keeps the legacy top-level app/dashboard route tree removed", () => {
    expect(existsSync(resolve(process.cwd(), "app/dashboard"))).toBe(false);
  });

  it("serves /dashboard from the authenticated (app) shell", () => {
    expect(
      existsSync(resolve(process.cwd(), "app/(app)/dashboard/page.tsx")),
    ).toBe(true);
  });

  it("does not redirect /dashboard away (TASK-FRT-183: / is the public landing)", () => {
    const source = readFileSync(resolve(process.cwd(), "next.config.mjs"), "utf-8");

    expect(source).not.toContain('source: "/dashboard"');
    expect(source).not.toContain('source: "/dashboard/:path*"');
  });
});
