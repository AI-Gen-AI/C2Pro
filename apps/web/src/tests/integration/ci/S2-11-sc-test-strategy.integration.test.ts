/**
 * Test Suite ID: S2-11
 * Roadmap Reference: S2-11 Three-layer SC test strategy (FLAG-13)
 */
import { describe, expect, it } from "vitest";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

describe("S2-11 RED - three-layer Server Component test strategy", () => {
  it("[S2-11-RED-01] documents the three layers and constraints in technical design", () => {
    const docPath = resolve(
      process.cwd(),
      "..",
      "..",
      "context",
      "C2PRO_TECHNICAL_DESIGN_DOCUMENT_v4_0.md",
    );
    const doc = readFileSync(docPath, "utf-8");

    expect(doc).toContain("### 8.3 Three-Layer Server Component Test Strategy (FLAG-13)");
    expect(doc).toContain("Layer 1 — Unit (Vitest + RTL):");
    expect(doc).toContain("Layer 2 — Integration (Vitest + MSW):");
    expect(doc).toContain("Layer 3 — E2E (Playwright):");
    expect(doc).toContain("CANNOT render async Server Components in jsdom");
  });

  it("[S2-11-RED-02] provides a dedicated architecture decision document for FLAG-13", () => {
    const strategyAdrPath = resolve(
      process.cwd(),
      "..",
      "..",
      "docs",
      "architecture",
      "decisions",
      "005-three-layer-sc-test-strategy.md",
    );

    expect(existsSync(strategyAdrPath)).toBe(true);

    const adr = readFileSync(strategyAdrPath, "utf-8");
    expect(adr).toContain("FLAG-13");
    expect(adr).toContain("Unit");
    expect(adr).toContain("Integration");
    expect(adr).toContain("E2E");
  });

  it("[S2-11-RED-03] tracks S2-11 completion in frontend sprint backlog", () => {
    const backlogPath = resolve(
      process.cwd(),
      "..",
      "..",
      "context",
      "C2PRO_TDD_BACKLOG_v1.0.md",
    );
    const backlog = readFileSync(backlogPath, "utf-8");

    expect(backlog).toContain("S2-11");
    expect(backlog).toContain("FLAG-13");
  });

  it("[S2-11-RED-04] enforces CI execution for all three test layers", () => {
    const ciPath = resolve(
      process.cwd(),
      "..",
      "..",
      ".github",
      "workflows",
      "frontend-ci.yml",
    );
    const ci = readFileSync(ciPath, "utf-8");

    expect(ci).toContain("pnpm test");
    expect(ci).toContain("pnpm test:e2e");
  });

  it("[S2-11-RED-05] defines a dedicated frontend E2E workflow", () => {
    const e2eWorkflowPath = resolve(
      process.cwd(),
      "..",
      "..",
      ".github",
      "workflows",
      "frontend-e2e.yml",
    );

    expect(existsSync(e2eWorkflowPath)).toBe(true);
  });
});
