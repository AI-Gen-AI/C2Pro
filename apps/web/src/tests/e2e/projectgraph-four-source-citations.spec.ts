/**
 * ProjectGraph CORE: real authenticated Alerts UI readout of a previously
 * computed Tier-2 snapshot on the SAME disposable four-document project.
 *
 * No route mocking, no programmatic token generation, no approval bypass.
 */
import { readFileSync, writeFileSync } from "node:fs";
import path from "node:path";

import { expect, test, type Page } from "@playwright/test";
import { requireExpectedOrganization, signInWithClerk } from "./support/p0b-auth";

type SourceAlert = {
  rule_code: string;
  source_clause_id: string | null;
  source_document_id: string | null;
  structured_ref_count: number;
  has_quote: boolean;
};
type PilotReceipt = {
  project_id?: string;
  snapshot_id?: string;
  source_authority?: Array<{ family: string; trusted: boolean }>;
  alert_read_model?: SourceAlert[];
};

const receiptPath = path.join(process.cwd(), "playwright-report", "projectgraph-functional-pilot.json");
const outputPath = path.join(process.cwd(), "playwright-report", "projectgraph-ui-citations.json");

async function signOut(page: Page): Promise<void> {
  const button = page.getByRole("button", { name: /user menu/i });
  await expect(button).toBeVisible({ timeout: 30_000 });
  await button.click();
  await page.getByRole("menuitem", { name: /sign out/i }).click();
  await page.waitForURL(/\/sign-in/, { timeout: 30_000 });
}

test("ProjectGraph four-source persisted alerts open real source citations after relogin", async ({
  browser,
  baseURL,
}) => {
  test.setTimeout(240_000);
  const receipt = JSON.parse(readFileSync(receiptPath, "utf8")) as PilotReceipt;
  const projectId = receipt.project_id;
  expect(projectId, "pilot must identify the actual four-file project").toMatch(/^[a-f0-9-]{36}$/);
  expect(receipt.snapshot_id, "ProjectGraph must have persisted a snapshot").toMatch(/^[a-f0-9-]{36}$/);
  expect(
    receipt.source_authority?.filter((source) => ["contract", "technical_spec"].includes(source.family) && source.trusted),
    "Contract and technical specification must have explicit trusted approval",
  ).toHaveLength(2);

  const expectedManifest = JSON.parse(readFileSync(
    path.join(process.cwd(), "src", "tests", "e2e", "test-data", "triplet", "triplet.manifest.json"),
    "utf8",
  )) as { expected_rules: string[]; expected_provisional: string[] };
  const expected = new Set([...expectedManifest.expected_rules, ...expectedManifest.expected_provisional]);
  const expectedAlerts = (receipt.alert_read_model ?? []).filter((alert) => expected.has(alert.rule_code));
  const addressable = expectedAlerts.filter(
    (alert) => alert.source_clause_id && alert.source_document_id && alert.has_quote,
  );
  const structured = expectedAlerts.filter(
    (alert) => alert.structured_ref_count > 0,
  );
  expect(
    addressable.length + structured.length,
    "Cannot demonstrate the ProjectGraph result without an original document/row citation",
  ).toBeGreaterThan(0);

  const context = await browser.newContext({ baseURL });
  const page = await context.newPage();
  try {
    await signInWithClerk(page);
    await requireExpectedOrganization(page);
    await page.goto("/projects/" + projectId + "/alerts");
    await expect(page.getByRole("heading", { name: "Alert Review Center" })).toBeVisible({
      timeout: 45_000,
    });
    await expect.poll(() => page.locator("table tbody tr").count(), { timeout: 35_000 })
      .toBeGreaterThan(0);

    const first = addressable[0];
    if (first) {
      const link = page.getByRole("link", { name: "View evidence for " + first.source_clause_id });
      await expect(link, "UI must expose the verified persisted contract clause link").toBeVisible({
        timeout: 30_000,
      });
      await link.click();
      await expect(page).toHaveURL(new RegExp("/projects/" + projectId + "/evidence\\?documentId="));
      expect(new URL(page.url()).searchParams.get("documentId")).toBe(first.source_document_id);
      await expect(page.getByText(/could not load|failed to load/i)).toHaveCount(0);
    } else {
      const link = page.getByRole("link", { name: /budget row|schedule activity/i }).first();
      await expect(link, "A structured source row must be a navigable link").toBeVisible({
        timeout: 30_000,
      });
      await link.click();
      await expect(page).toHaveURL(new RegExp("/projects/" + projectId + "/evidence\\?documentId="));
      await expect(page.getByText(/could not load|failed to load/i)).toHaveCount(0);
    }

    // Preserve the exact same user/project, but require an actual new Clerk sign-in.
    await signOut(page);
    await page.goto("/projects/" + projectId + "/alerts");
    await expect(page).toHaveURL(/\/sign-in/, { timeout: 30_000 });
    await signInWithClerk(page);
    await requireExpectedOrganization(page);
    await page.goto("/projects/" + projectId + "/alerts");
    await expect(page.getByRole("heading", { name: "Alert Review Center" })).toBeVisible({
      timeout: 45_000,
    });
    await expect.poll(() => page.locator("table tbody tr").count(), { timeout: 35_000 })
      .toBeGreaterThan(0);
    writeFileSync(outputPath, JSON.stringify({
      state: "PASS",
      project_id: projectId,
      snapshot_id: receipt.snapshot_id,
      persisted_alert_records: receipt.alert_read_model?.length ?? 0,
      addressable_citations: addressable.length,
      structured_citations: structured.length,
      real_clerk_relogin: true,
      ui_source_navigation: true,
    }, null, 2) + "\n");
  } finally {
    await context.close();
  }
});
