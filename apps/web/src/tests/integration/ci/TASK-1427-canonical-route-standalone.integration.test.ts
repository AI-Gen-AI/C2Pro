/**
 * Test Suite ID: TASK-1427
 * Route Coverage: canonical app routes must not depend on legacy dashboard files
 */
import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

function readRoute(pathFromWebRoot: string): string {
  return readFileSync(resolve(process.cwd(), pathFromWebRoot), "utf-8");
}

describe("TASK-1427 canonical route standalone enforcement", () => {
  it("keeps the canonical dashboard landing page independent from app/dashboard", () => {
    const source = readRoute("app/(app)/page.tsx");

    expect(source).not.toMatch(/dashboard\/page/);
    expect(source).not.toMatch(/export\s+\{\s*default\s*\}\s+from/);
  });

  it("keeps the canonical project budget route independent from app/dashboard", () => {
    const source = readRoute("app/(app)/projects/[id]/budget/page.tsx");

    expect(source).not.toMatch(/dashboard\/projects\/\[id\]\/budget\/page/);
    expect(source).not.toMatch(/export\s+\{\s*default\s*\}\s+from/);
  });

  it("keeps the canonical project WBS route independent from app/dashboard", () => {
    const source = readRoute("app/(app)/projects/[id]/wbs/page.tsx");

    expect(source).not.toMatch(/dashboard\/projects\/\[id\]\/wbs\/page/);
    expect(source).not.toMatch(/export\s+\{\s*default\s*\}\s+from/);
  });
});
