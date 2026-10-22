// Fail-closed check for the nightly RED backlog inventory.
// Usage: node scripts/playwright-red-backlog-ran.mjs <results.json>
// RED specs may fail (that is expected), but the inventory itself only counts
// when the auth setup succeeded and at least one red-backlog test executed.
import fs from "node:fs";

const SETUP_PROJECTS = new Set(["global-setup", "setup"]);
const file = process.argv[2];

const fail = (message) => {
  console.log(`::error::RED backlog NOT EXECUTED: ${message}`);
  process.exit(1);
};

if (!file || !fs.existsSync(file) || fs.statSync(file).size === 0) {
  fail("no Playwright results were produced.");
}

const { suites = [] } = JSON.parse(fs.readFileSync(file, "utf8"));
const tests = [];
const walk = (suite) => {
  for (const spec of suite.specs || []) tests.push(...spec.tests);
  for (const child of suite.suites || []) walk(child);
};
suites.forEach(walk);

const failedSetup = tests.filter(
  (t) => SETUP_PROJECTS.has(t.projectName) && t.status === "unexpected",
);
if (failedSetup.length) fail("the Clerk auth setup failed, so no RED spec ran.");

const executed = tests.filter(
  (t) =>
    t.projectName === "red-backlog" &&
    (t.results || []).some((r) => r.status && r.status !== "skipped"),
);
if (!executed.length) fail("no red-backlog test executed.");

console.log(`RED backlog executed ${executed.length} test(s).`);
