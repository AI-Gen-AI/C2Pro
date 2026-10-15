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
import {
  requireProductionApiOrigin,
  requireProductionOrigin,
} from "./support/prod-preflight";

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

type ObservedRevisionPanel = {
  apiOrigin: string;
  // Only held in test process memory; never included in output or exceptions.
  protectedClauseText: string[];
};

async function assertRevisionPanel(page: Page): Promise<ObservedRevisionPanel> {
  const apiHistory = page.waitForResponse(
    (r) =>
      r.request().method() === "GET" &&
      new URL(r.url()).pathname ===
        `/api/v1/documents/${DOCUMENT_ID}/revisions`,
    { timeout: 60_000 },
  );

  await page.goto(`/projects/${PROJECT_ID}/evidence?documentId=${DOCUMENT_ID}`);
  const authorizedHistory = await apiHistory;
  expect(authorizedHistory.status()).toBe(200);
  const liveApiOrigin = new URL(authorizedHistory.url()).origin;
  // Only accept the existing vetted production frontend proxy or backend API.
  if (liveApiOrigin !== requireProductionOrigin(page.url())) {
    requireProductionApiOrigin(liveApiOrigin);
  }

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
  await expect(preview.getByText(new RegExp(REV_A_ID))).toBeVisible();
  const clauseTextA = await preview.getByRole("listitem").allTextContents();

  await panel.getByRole("button", { name: /^Revision 2 —/ }).click();
  await expect(
    preview.getByText(/7 stored clauses in this selected revision/i),
  ).toBeVisible();
  await expect(preview.getByText(/Proposed — not trusted/i)).toBeVisible();
  await expect(preview.getByRole("listitem")).toHaveCount(7);
  await expect(preview.getByText(new RegExp(REV_B_ID))).toBeVisible();
  const clauseTextB = await preview.getByRole("listitem").allTextContents();

  // Frontend controls must not advertise a fabricated trusted-current basis.
  await expect(
    panel.getByRole("button", { name: /Trusted current/i }),
  ).toHaveCount(0);
  return {
    apiOrigin: liveApiOrigin,
    protectedClauseText: [...clauseTextA, ...clauseTextB],
  };
}

test("existing A9/B7 remains revision-scoped after real production relogin", async ({
  page,
  browser,
}) => {
  requireExactSyntheticTarget();

  // Observe the entire qualification lifecycle, including login/logout.
  // Clerk's own cross-origin session requests are excluded; product/API
  // writes on the approved C2Pro frontend/backend are forbidden.
  let observedProductWriteRequests = 0;
  page.on("request", (request) => {
    const method = request.method().toUpperCase();
    if (method === "GET" || method === "HEAD" || method === "OPTIONS") return;
    let url: URL;
    try {
      url = new URL(request.url());
    } catch {
      observedProductWriteRequests += 1; // Unknown write target: fail closed.
      return;
    }
    const validHost = [
      "c2pro.io",
      "www.c2pro.io",
      "c2pro-production.up.railway.app",
    ].includes(url.hostname);
    const productApi = url.pathname.startsWith("/api/") &&
      !url.pathname.startsWith("/api/runtime/");
    if (validHost && productApi) observedProductWriteRequests += 1;
  });

  await signInSyntheticProductionUser(page);
  const authorized = await assertRevisionPanel(page);
  const provenApiOrigin = authorized.apiOrigin;

  await signOutThroughUi(page);

  // A fresh, cookie-free browser context, without bearer or Clerk session,
  // must NOT be able to read this qualified synthetic document.
  const frontendOrigin = requireProductionOrigin(page.url());
  const anon = await browser.newContext({
    baseURL: frontendOrigin,
    storageState: { cookies: [], origins: [] },
  });
  try {
    // Cover BOTH revision metadata and the actual clause-text endpoint.
    // Rejecting one while exposing /entities would leak contract evidence.
    // The authenticated 200 establishes that this is a REAL endpoint,
    // so an accidental 404 from a different API host cannot pass the test.
    // Also exercise the frontend's same-origin proxy, if distinct.
    for (const origin of new Set([provenApiOrigin, frontendOrigin])) {
      if (origin !== frontendOrigin) requireProductionApiOrigin(origin);
      for (const endpoint of [
        `/api/v1/documents/${DOCUMENT_ID}/revisions`,
        `/api/v1/documents/${DOCUMENT_ID}/entities`,
        `/api/v1/documents/${DOCUMENT_ID}/entities?revision_id=${REV_A_ID}`,
        `/api/v1/documents/${DOCUMENT_ID}/entities?revision_id=${REV_B_ID}`,
      ]) {
        const response = await anon.request.get(origin + endpoint, {
          maxRedirects: 0,
          failOnStatusCode: false,
        });
        const status = response.status();
        const denied = [401, 403, 404].includes(status);
        const loginRedirect =
          [302, 303, 307, 308].includes(status) &&
          /sign-in|sign_in|login|clerk/i.test(
            response.headers()["location"] ?? "",
          );
        expect(
          denied || loginRedirect,
          "Anonymous revision or clause-data API returned a non-denial",
        ).toBe(true);

        // HTTP denial alone is NOT proof of confidentiality. Fail closed if
        // any known revision ID or in-memory synthetic clause content leaked
        // through an error response. Never log the body or clause strings.
        const deniedBody = (await response.body()).toString("utf8");
        const normalizedBody = deniedBody.replace(/\s+/g, " ").toLowerCase();
        const leakedIdentifier = [REV_A_ID, REV_B_ID].some((id) =>
          normalizedBody.includes(id.toLowerCase()),
        );
        const leakedClause = authorized.protectedClauseText.some((text) => {
          const canonical = text.replace(/\s+/g, " ").trim().toLowerCase();
          // Scan overlapping sliding fragments, not just the clause prefix.
          // Diagnostic proxies could reveal an excerpt from the middle.
          if (canonical.length < 16) return normalizedBody.includes(canonical);
          for (let offset = 0; offset <= canonical.length - 16; offset += 12) {
            const fragment = canonical.slice(offset, offset + 32);
            if (normalizedBody.includes(fragment)) return true;
          }
          return normalizedBody.includes(canonical.slice(-16));
        });
        // Only a small, flat error envelope is an acceptable API denial.
        // Reject unexpected JSON structures, including nested arrays/objects
        // under "detail", without ever printing an error response body.
        let structuredDataLeak = false;
        if (denied) {
          if (!/application\/json/i.test(response.headers()["content-type"] ?? "")) {
            structuredDataLeak = true;
          } else {
            try {
              const payload: unknown = JSON.parse(deniedBody);
              structuredDataLeak =
                typeof payload !== "object" ||
                payload === null ||
                Array.isArray(payload) ||
                Object.keys(payload).length === 0 ||
                !Object.entries(payload).every(
                  ([key, value]) =>
                    ["detail", "error", "message"].includes(key) &&
                    typeof value === "string",
                );
            } catch {
              structuredDataLeak = true;
            }
          }
        }
        expect(
          leakedIdentifier || leakedClause || structuredDataLeak,
          "Denial response leaked synthetic revision/clause evidence",
        ).toBe(false);
      }
    }
  } finally {
    await anon.close();
  }

  await signInSyntheticProductionUser(page);
  expect((await assertRevisionPanel(page)).apiOrigin).toBe(provenApiOrigin);
  await signOutThroughUi(page);
  expect(
    observedProductWriteRequests,
    "Production QA emitted a product/API write request",
  ).toBe(0);

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
        anonymous_clause_entities_denied: true,
        denial_payload_non_disclosure: true,
        second_tenant_principal_isolation: "NOT_VERIFIED",
        source_pdf_navigation: "NOT_VERIFIED",
        lifecycle_authority: false,
        product_write_requests_observed: observedProductWriteRequests,
        database_side_effects: "NOT_VERIFIED",
        credential_material_recorded: false,
        revision_ids_matched_expected: true,
      },
      null,
      2,
    ),
    "utf8",
  );
});
