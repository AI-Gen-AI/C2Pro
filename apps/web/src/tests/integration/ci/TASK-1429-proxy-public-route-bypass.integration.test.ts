/**
 * Test Suite ID: TASK-1429
 * Backlog Task: TASK-1429
 */
import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

describe("TASK-1429 RED - proxy matcher excludes public and demo routes", () => {
  it("[TASK-1429-RED-01] keeps the root landing route out of Clerk proxy matching", () => {
    const proxyPath = resolve(process.cwd(), "proxy.ts");
    const proxySource = readFileSync(proxyPath, "utf8");

    expect(proxySource).toContain("(?!$|_next|");
  });

  it("[TASK-1429-RED-02] excludes demo and public auth routes at the matcher level, not only inside isPublicRoute", () => {
    const proxyPath = resolve(process.cwd(), "proxy.ts");
    const proxySource = readFileSync(proxyPath, "utf8");

    expect(proxySource).toContain("demo(?:/|$)");
    expect(proxySource).toContain("sign-in(?:/|$)");
    expect(proxySource).toContain("login(?:/|$)");
    expect(proxySource).toContain("api/webhooks/clerk(?:/|$)");
  });
});
