// Fail-closed check for the nightly RED backlog inventory (CLI: playwright-red-backlog-ran.mjs).
// RED specs may fail (that is expected), but the inventory itself only counts
// when the auth setup succeeded and at least one red-backlog test executed.
import fs from "node:fs";

const SETUP_PROJECTS = new Set(["global-setup", "setup"]);
// The nightly job writes the report here; the path is never taken from input.
export const REPORT_PATH = "playwright-report/red-backlog-results.json";

/** Why a parsed Playwright JSON report is not a RED inventory, or null. */
export function redBacklogProblem(report) {
  if (!report || typeof report !== "object") return "no Playwright results were produced.";
  const tests = [];
  const walk = (suite) => {
    for (const spec of suite.specs || []) tests.push(...spec.tests);
    for (const child of suite.suites || []) walk(child);
  };
  (report.suites || []).forEach(walk);

  if (tests.some((t) => SETUP_PROJECTS.has(t.projectName) && t.status === "unexpected")) {
    return "the Clerk auth setup failed, so no RED spec ran.";
  }
  const executed = tests.filter(
    (t) =>
      t.projectName === "red-backlog" &&
      (t.results || []).some((r) => r.status && r.status !== "skipped"),
  );
  return executed.length ? null : "no red-backlog test executed.";
}

/** CLI entry: returns the process exit code for the report at file. */
export function main(file = REPORT_PATH, log = console.log) {
  const report =
    fs.existsSync(file) && fs.statSync(file).size > 0
      ? JSON.parse(fs.readFileSync(file, "utf8"))
      : null;
  const problem = redBacklogProblem(report);
  if (problem) {
    log(`::error::RED backlog NOT EXECUTED: ${problem}`);
    return 1;
  }
  log("RED backlog executed.");
  return 0;
}
