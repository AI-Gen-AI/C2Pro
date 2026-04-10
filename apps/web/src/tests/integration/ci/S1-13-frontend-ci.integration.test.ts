/**
 * Test Suite ID: TS-INT-FRT-CI-001
 */

import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

describe("S1-13 frontend CI pipeline", () => {
  it("defines the required quality gates in GitHub Actions", () => {
    const workflowPath = resolve(
      process.cwd(),
      "..",
      "..",
      ".github",
      "workflows",
      "frontend-ci.yml",
    );
    const workflow = readFileSync(workflowPath, "utf-8");

    expect(workflow).toContain("name: Frontend CI");
    expect(workflow).toContain("working-directory: apps/web");
    expect(workflow).toContain("pnpm typecheck");
    expect(workflow).toContain("pnpm lint");
    expect(workflow).toContain("pnpm test");
    expect(workflow).toContain("pnpm generate:api:check");
  });

  it("pins the frontend production build to the webpack path verified in Vercel parity fixes", () => {
    const packageJsonPath = resolve(process.cwd(), "package.json");
    const packageJson = JSON.parse(readFileSync(packageJsonPath, "utf-8")) as {
      scripts?: Record<string, string>;
    };

    expect(packageJson.scripts?.build).toBe(
      "node ./scripts/clean-next-build.mjs && next build --webpack",
    );
  });
});
