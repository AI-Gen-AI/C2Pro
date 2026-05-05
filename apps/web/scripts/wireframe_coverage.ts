/**
 * TASK-QA-207 — Wireframe coverage tracker.
 *
 * Scans all *.wireframe.test.tsx files under apps/web for
 *   export const WIREFRAME_REF = "docs/wireframes/XX.md[#section]"
 * declarations, then cross-checks against docs/wireframes/0*.md.
 *
 * Outputs:
 *   apps/web/wireframe-coverage.json   (always written)
 *
 * Exit codes:
 *   0 — every 0*.md wireframe has at least one covering test
 *   1 — one or more wireframes have zero coverage
 *
 * Usage:
 *   npx tsx apps/web/scripts/wireframe_coverage.ts [--ci]
 */

import fs from "node:fs";
import path from "node:path";

const REPO_ROOT = path.resolve(import.meta.dirname, "../../..");
const WIREFRAMES_DIR = path.join(REPO_ROOT, "docs", "wireframes");
const WEB_ROOT = path.join(REPO_ROOT, "apps", "web");
const OUTPUT_PATH = path.join(WEB_ROOT, "wireframe-coverage.json");

// ── 1. Collect canonical wireframes (docs/wireframes/0*.md) ────────────────

function collectWireframes(): string[] {
  return fs
    .readdirSync(WIREFRAMES_DIR)
    .filter((f) => /^0\d-.*\.md$/.test(f))
    .map((f) => `docs/wireframes/${f}`)
    .sort();
}

// ── 2. Scan test files for WIREFRAME_REF exports ───────────────────────────

interface TestFileRef {
  file: string;
  refs: string[];
}

const REF_PATTERN = /WIREFRAME_REF\s*=\s*["'`]([^"'`]+)["'`]/g;

function extractRefs(filePath: string): string[] {
  const src = fs.readFileSync(filePath, "utf-8");
  const refs: string[] = [];
  for (const match of src.matchAll(REF_PATTERN)) {
    refs.push(match[1].split("#")[0].trim());
  }
  return refs;
}

function walkDir(dir: string, suffix: string, results: string[] = []): string[] {
  if (!fs.existsSync(dir)) return results;
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      walkDir(full, suffix, results);
    } else if (entry.isFile() && entry.name.endsWith(suffix)) {
      results.push(full);
    }
  }
  return results;
}

function collectTestRefs(): TestFileRef[] {
  const dir = path.join(WEB_ROOT, "src", "tests", "wireframes");
  const files = walkDir(dir, ".wireframe.test.tsx");
  return files.map((f) => ({
    file: path.relative(REPO_ROOT, f).replace(/\\/g, "/"),
    refs: extractRefs(f),
  }));
}

// ── 3. Build coverage map ──────────────────────────────────────────────────

interface WireframeCoverage {
  wireframe: string;
  covered: boolean;
  tests: string[];
}

interface CoverageReport {
  generated_at: string;
  total_wireframes: number;
  covered: number;
  uncovered: number;
  coverage_pct: number;
  wireframes: WireframeCoverage[];
}

function buildReport(
  wireframes: string[],
  testRefs: TestFileRef[],
): CoverageReport {
  const refMap = new Map<string, string[]>();
  for (const wf of wireframes) {
    refMap.set(wf, []);
  }

  for (const { file, refs } of testRefs) {
    for (const ref of refs) {
      const key = wireframes.find((wf) => wf === ref || ref.startsWith(wf));
      if (key) {
        refMap.get(key)!.push(file);
      }
    }
  }

  const entries: WireframeCoverage[] = [];
  for (const [wf, tests] of refMap) {
    entries.push({ wireframe: wf, covered: tests.length > 0, tests });
  }

  const covered = entries.filter((e) => e.covered).length;
  return {
    generated_at: new Date().toISOString(),
    total_wireframes: entries.length,
    covered,
    uncovered: entries.length - covered,
    coverage_pct: entries.length
      ? Math.round((covered / entries.length) * 100)
      : 0,
    wireframes: entries,
  };
}

// ── 4. Main ────────────────────────────────────────────────────────────────

const isCi = process.argv.includes("--ci");

const wireframes = collectWireframes();
const testRefs = collectTestRefs();
const report = buildReport(wireframes, testRefs);

fs.writeFileSync(OUTPUT_PATH, JSON.stringify(report, null, 2), "utf-8");

console.log(`\nWireframe Coverage Report`);
console.log(`  Wireframes : ${report.total_wireframes}`);
console.log(`  Covered    : ${report.covered}`);
console.log(`  Uncovered  : ${report.uncovered}`);
console.log(`  Coverage   : ${report.coverage_pct}%`);
console.log(`  Output     : ${path.relative(process.cwd(), OUTPUT_PATH)}\n`);

if (report.uncovered > 0) {
  console.error("Missing coverage for:");
  for (const e of report.wireframes.filter((e) => !e.covered)) {
    console.error(`  ✗  ${e.wireframe}`);
  }
  if (isCi) {
    process.exit(1);
  }
} else {
  console.log("✓  All wireframes have at least one covering test.");
}
