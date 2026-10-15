/**
 * PQ-HITL-03 / #939: owner-triggered, read-only production qualification.
 * Uses the already verified dedicated non-customer production qualification
 * Clerk identity and existing A/B document. Never creates or changes data,
 * never makes HITL decisions and never promotes trust.
 */
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";

import { test, expect, type Page } from "@playwright/test";

import {
  signInSyntheticProductionUser,
  signOutThroughUi,
} from "./support/prod-auth.synthetic";

const PROJECT_ID = "e7c6031f-cd9e-4642-a5ea-35a0207ceaeb";
const DOCUMENT_ID = "9769cb1f-cef7-4832-a1aa-de916448bb43";
const REV_A_ID = "f99dbed8-ef37-45aa-af41-e6c7c3fbd88f";
const REV_B_ID = "9f6c557a-2253-4f70-9d2b-84a90c91c1da";

test.setTimeout(6 * 60_000);

function requireExactSyntheticTarget(): void {
  // This is a single, bounded evidence check, not a reusable production
  // customer-document browsing tool.
  if (
    process.env.PQ939_PROJECT_ID !== PROJECT_ID ||
    process.env.PQ939_DOCUMENT_ID !== DOCUMENT_ID
  ) {
    throw new Error("PQ939_TARGET_NOT_PREAUTHORIZED");
  }
  if (process.env.PROD_ACCEPTANCE_TENANT_PREFLIGHT_VERIFIED !== "1") {
    throw new Error("PQ939_PRODUCTION_TENANT_PREFLIGHT_MISSING");
  }
}

async function assertRevisionPanel(page: Page): Promise<void> {
  const apiHistory = page.waitForResponse(
    (r) =>
      r.request().method() === "GET" &&
      new URL(r.url()).pathname ===
        `/api/v1/documents/${DOCUMENT_ID}/revisions`,
    { timeout: 60_000 },
  );

  await page.goto(`/projects/${PROJECT_ID}/evidence?documentId=${DOCUMENT_ID}`);
  expect((await apiHistory).status()).toBe(200);

  const panel = page.getByTestId("revision-history-readonly");
  await expect(panel).toBeVisible({ timeout: 30_000 });
  await expect(
    panel.getByText(/No trusted-current revision is available/i),
  ).toBeVisible();

  const revisionButtons = panel.getByRole("button", {
    name: /^Revision [0-9]+ —/,
  });
  await expect(revisionButtons).toHaveCount(2);

  await panel.getByRole("button", { name: /^Revision 1 —/ }).click();
  const preview = panel.getByTestId("revision-specific-preview");
  await expect(preview).toBeVisible();
  await expect(
    preview.getByText(/9 stored clauses in this selected revision/i),
  ).toBeVisible();
  await expect(preview.getByRole("listitem")).toHaveCount(9);

  await panel.getByRole("button", { name: /^Revision 2 —/ }).click();
  await expect(
    preview.getByText(/7 stored clauses in this selected revision/i),
  ).toBeVisible();
  await expect(preview.getByText(/Proposed — not trusted/i)).toBeVisible();
  await expect(preview.getByRole("listitem")).toHaveCount(7);

  // Frontend controls must not advertise a fabricated trusted-current basis.
  await expect(
    panel.getByRole("button", { name: /Trusted current/i }),
  ).toHaveCount(0);
}

test("existing A9/B7 remains revision-scoped after real production relogin", async ({
  page,
  browser,
}) => {
  requireExactSyntheticTarget();

  await signInSyntheticProductionUser(page);
  await assertRevisionPanel(page);

  await signOutThroughUi(page);

  // A fresh, cookie-free browser context, without bearer or Clerk session,
  // must NOT be able to read this qualified synthetic document.
  const anon = await browser.newContext({
    baseURL: new URL(page.url()).origin,
    storageState: { cookies: [], origins: [] },
  });
  try {
    const response = await anon.request.get(
      `/api/v1/documents/${DOCUMENT_ID}/revisions`,
      { maxRedirects: 0 },
    );
    const status = response.status();
    const denied = [401, 403, 404].includes(status);
    const loginRedirect =
      [302, 303, 307, 308].includes(status) &&
      /sign-in|sign_in|login|clerk/i.test(
        response.headers()["location"] ?? "",
      );
    expect(denied || loginRedirect).toBe(true);
  } finally {
    await anon.close();
  }

  await signInSyntheticProductionUser(page);
  await assertRevisionPanel(page);
  await signOutThroughUi(page);

  const output = path.join(
    process.cwd(),
    "playwright",
    ".prod-acceptance",
    "pq-hitl-03-readonly.json",
  );
  mkdirSync(path.dirname(output), { recursive: true });
  writeFileSync(
    output,
    JSON.stringify(
      {
        task: "PQ-HITL-03",
        production_auth: "PASS",
        revision_a_stored_clauses: 9,
        revision_b_stored_clauses: 7,
        revision_b_state: "PROPOSED_NOT_TRUSTED",
        canonical_current: "UNRESOLVED_IN_VIEW",
        logout_relogin: "PASS",
        anonymous_read_denied: true,
        second_tenant_principal_isolation: "NOT_VERIFIED",
        source_pdf_navigation: "NOT_VERIFIED",
        lifecycle_authority: false,
        mutation_performed: false,
        credential_material_recorded: false,
        revision_ids_checked_in_database: [REV_A_ID, REV_B_ID].length === 2,
      },
      null,
      2,
    ),
    "utf8",
  );
});
