// Markdown summary of a Playwright JSON report for $GITHUB_STEP_SUMMARY.
// Usage: node scripts/playwright-summary.cjs <results.json> "<title>"
// Prints NOT EXECUTED when the report is missing; never alters the exit status.
const fs = require("fs");

const [file, title] = process.argv.slice(2);
console.log(`## ${title}\n`);
if (!file || !fs.existsSync(file)) {
  console.log("**NOT EXECUTED**: no Playwright results were produced.");
  process.exit(0);
}
const { stats, suites = [] } = JSON.parse(fs.readFileSync(file, "utf8"));
console.log("| passed | failed | flaky | skipped |\n|---:|---:|---:|---:|");
console.log(`| ${stats.expected} | ${stats.unexpected} | ${stats.flaky} | ${stats.skipped} |\n`);
const byStatus = { unexpected: [], expected: [] };
const walk = (suite, path) => {
  for (const spec of suite.specs || []) {
    for (const t of spec.tests) {
      if (t.status in byStatus) {
        byStatus[t.status].push(`${spec.file}: ${[...path, spec.title].join(" › ")}`);
      }
    }
  }
  for (const child of suite.suites || []) walk(child, [...path, child.title]);
};
suites.forEach((s) => walk(s, []));
const list = (label, items) => {
  if (!items.length) return;
  console.log(`<details><summary>${items.length} ${label}</summary>\n`);
  items.forEach((item) => console.log(`- ${item}`));
  console.log("\n</details>\n");
};
list("failing", byStatus.unexpected);
if (process.env.SUMMARY_LIST_PASSING === "1") list("passing", byStatus.expected);
