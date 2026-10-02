/**
 * Test Suite ID: TASK-QA-336
 * Ensures the non-blocking nightly lane executes only the Chromium project.
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

describe("TASK-QA-336 nightly full E2E lane", () => {
  it("[TASK-QA-336-RED-01] runs the local Playwright binary with the Chromium project", () => {
    const workflowPath = resolve(process.cwd(), "..", "..", ".github", "workflows", "nightly-full-e2e.yml");
    const workflow = readFileSync(workflowPath, "utf8");

    expect(workflow).toContain("run: ./node_modules/.bin/playwright test --project=chromium");
    expect(workflow).toContain("env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY != '' && (env.CLERK_SECRET_KEY != '' || env.CLERK_TESTING_TOKEN != '')");
    expect(workflow).not.toContain("pk_test_Y2xlcmsubW9jay5sb2NhbCQ");
  });

  it("[TASK-QA-336-RED-02] gates the seeded Chromium smoke lane behind RUN_FULL_E2E", () => {
    const workflowPath = resolve(process.cwd(), "..", "..", ".github", "workflows", "ci.yml");
    const workflow = readFileSync(workflowPath, "utf8");

    expect(workflow).toContain("vars.RUN_FULL_E2E == 'true'");
    expect(workflow).toContain(
      "./node_modules/.bin/playwright test src/tests/e2e/coherence-v1.spec.ts --project=chromium",
    );
    expect(workflow).toContain(
      "./node_modules/.bin/playwright test src/tests/e2e/journeys/journey-3-wedge.spec.ts --grep '@real-backend' --project=chromium",
    );
    expect(workflow).toContain(
      "env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY != '' && (env.CLERK_SECRET_KEY != '' || env.CLERK_TESTING_TOKEN != '')",
    );
    const smokeJob = workflow.slice(
      workflow.indexOf("frontend-e2e-smoke:"),
      workflow.indexOf("frontend-build:"),
    );
    expect(smokeJob).not.toContain("pk_test_Y2xlcmsubW9jay5sb2NhbCQ");
    expect(smokeJob).toContain("Set repo variable RUN_FULL_E2E=true to make this gate blocking.");
    expect(smokeJob).toContain("- name: Build frontend for E2E smoke");
    expect(smokeJob).toContain("run: pnpm build");
    expect(smokeJob).toContain("PLAYWRIGHT_WEBSERVER_MODE: production");
    expect(workflow).not.toContain(
      "run: pnpm test:e2e -- src/tests/e2e/coherence-v1.spec.ts src/tests/e2e/journeys/journey-3-wedge.spec.ts --project=chromium",
    );
  });

  it("[TASK-QA-336-RED-03] reconciles the Clerk Organization before seeding the real-backend smoke", () => {
    const workflowPath = resolve(process.cwd(), "..", "..", ".github", "workflows", "ci.yml");
    const workflow = readFileSync(workflowPath, "utf8");
    const smokeJob = workflow.slice(
      workflow.indexOf("frontend-e2e-smoke:"),
      workflow.indexOf("frontend-build:"),
    );

    const reconcile = smokeJob.indexOf(
      "- name: Reconcile dedicated Clerk E2E Organization fixture",
    );
    const seed = smokeJob.indexOf("- name: Seed FRT-192 full-stack E2E wedge");
    expect(reconcile).toBeGreaterThan(-1);
    expect(seed).toBeGreaterThan(reconcile);
    expect(smokeJob).toContain(
      "run: python apps/api/scripts/provision_clerk_e2e_fixture.py",
    );
  });

  it("[TASK-QA-336-RED-04] keeps dev as the Playwright default but supports production smoke", () => {
    const configPath = resolve(process.cwd(), "playwright.config.ts");
    const config = readFileSync(configPath, "utf8");

    expect(config).toContain('process.env.PLAYWRIGHT_WEBSERVER_MODE === "production"');
    expect(config).toContain('"pnpm start --hostname localhost --port 3100"');
    expect(config).toContain('"pnpm dev --hostname localhost --port 3100 --webpack"');
  });
});
