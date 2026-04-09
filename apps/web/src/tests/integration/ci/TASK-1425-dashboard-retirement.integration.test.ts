/**
 * Test Suite ID: TASK-1425
 * Route Coverage: legacy dashboard tree retirement with URL compatibility redirects
 */
import { describe, expect, it } from "vitest";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

describe("TASK-1425 dashboard route retirement", () => {
  it("removes the legacy app/dashboard route tree", () => {
    expect(existsSync(resolve(process.cwd(), "app/dashboard"))).toBe(false);
  });

  it("keeps legacy /dashboard URLs compatible through next config redirects", () => {
    const source = readFileSync(resolve(process.cwd(), "next.config.mjs"), "utf-8");

    expect(source).toContain("async redirects()");
    expect(source).toContain("source: \"/dashboard\"");
    expect(source).toContain("destination: \"/\"");
    expect(source).toContain("source: \"/dashboard/:path*\"");
    expect(source).toContain("destination: \"/:path*\"");
  });
});
