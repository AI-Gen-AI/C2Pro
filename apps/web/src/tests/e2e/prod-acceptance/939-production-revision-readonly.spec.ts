/**
 * PQ-HITL-03 / #939: owner-triggered, read-only production qualification.
 * Uses the already verified dedicated non-customer production qualification
 * Clerk identity and existing A/B document. Never creates or changes data,
 * never makes HITL decisions and never promotes trust.
 */
import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";

import { test, expect, type Page, type Request } from "@playwright/test";

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

// Stable four-field, category-only diagnostics: never emit raw method/URL/header.
function nonReadCategory(
  rawMethod: string,
  host: "frontend" | "railway" | "unknown_origin",
  route: string,
  nextActionPresent: boolean,
): string {
  const method = ["POST", "PUT", "PATCH", "DELETE", "CONNECT", "TRACE"].includes(rawMethod)
    ? rawMethod
    : "other";
  return `${method}:${host}:${route}:${nextActionPresent}`;
}

// Extra defence: this bounded exception relies on no app-authored Server Actions
// in the checked-out Next frontend source. Clerk's versioned SDK owns its
// internal auth/session operations; any new native app actions force review.
// This conservative scan is not a substitute for runtime side-effect checks.
function requireNoExplicitAppServerActions(): void {
  try {
    const candidates = execFileSync(
      "git",
      [
        "grep", "-l", "--fixed-strings",
        "-e", "'use server'", "-e", '"use server"',
        "HEAD", "--",
        "apps/web/app", "apps/web/components", "apps/web/hooks",
        "apps/web/lib", "apps/web/stores", "apps/web/contexts",
      ],
      { encoding: "utf8", timeout: 10_000 },
    );
    if (candidates.trim()) {
      throw new Error("PQ939_APP_SERVER_ACTION_SOURCE_REQUIRES_REVIEW");
    }
  } catch (error) {
    // git grep exit 1 strictly means no source matches. Everything else,
    // including an unavailable git executable, fails the precondition.
    if ((error as { status?: number }).status === 1) return;
    throw error;
  }
}

function evidenceFingerprint(clauseText: string[]): string {
  return createHash("sha256")
    .update(JSON.stringify([...clauseText].sort()))
    .digest("hex");
}

type ObservedRevisionPanel = {
  apiOrigin: string;
  // This exact revision endpoint yielded HTTP 200 with real Clerk auth.
  // Reuse it for anonymous negatives instead of guessing a proxy route.
  revisionPath: string;
  // Only held in test process memory; never included in output or exceptions.
  protectedClauseText: string[];
};

async function assertRevisionPanel(page: Page): Promise<ObservedRevisionPanel> {
  const apiHistory = page.waitForResponse(
    (r) => {
      const pathname = new URL(r.url()).pathname;
      // Orval strips /api/v1 for the default same-origin /api proxy;
      // direct backend calls keep /api/v1. Accept only these two routes.
      return (
        r.request().method() === "GET" &&
        [
          `/api/documents/${DOCUMENT_ID}/revisions`,
          `/api/v1/documents/${DOCUMENT_ID}/revisions`,
        ].includes(pathname)
      );
    },
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
    revisionPath: new URL(authorizedHistory.url()).pathname,
    protectedClauseText: [...clauseTextA, ...clauseTextB],
  };
}

test("existing A9/B7 remains revision-scoped after real production relogin", async ({
  page,
  browser,
}) => {
  requireExactSyntheticTarget();
  requireNoExplicitAppServerActions();

  // Observe the entire qualification lifecycle, including login/logout.
  // Clerk's own cross-origin session requests are excluded; product/API
  // writes on the approved C2Pro frontend/backend are forbidden.
  let observedProductWriteRequests = 0;
  // Login and logout require Clerk's session/Organization control-plane
  // updates. The previous real run observed exactly one Next-Action POST on
  // /sign-in and one on this synthetic evidence page per session. Do NOT
  // conflate these known, narrowly scoped auth transitions with a business
  // document mutation. Unknown Next actions and ALL API non-reads still FAIL.
  let session: 0 | 1 | 2 = 1;
  const observedClerkTransitions = new Map<string, number>();
  const clerkTransitionRequests: Request[] = [];
  // Never record URL strings, query parameters, opaque Next action IDs,
  // request bodies, headers or protected document identifiers. Category only.
  const observedNonReadCategories = new Map<string, number>();
  page.on("request", (request) => {
    const method = request.method().toUpperCase();
    if (method === "GET" || method === "HEAD" || method === "OPTIONS") return;
    let url: URL;
    try {
      url = new URL(request.url());
    } catch {
      observedProductWriteRequests += 1; // Unknown write target: fail closed.
      const category = nonReadCategory(method, "unknown_origin", "unparseable", false);
      observedNonReadCategories.set(
        category,
        (observedNonReadCategories.get(category) ?? 0) + 1,
      );
      return;
    }
    const validHost = [
      "c2pro.io",
      "www.c2pro.io",
      "c2pro-production.up.railway.app",
    ].includes(url.hostname);
    // Include server actions/form POSTs outside /api/ as well.
    // Clerk's separate account/auth hosts are not among these app origins.
    if (validHost) {
      const originCategory =
        url.hostname === "c2pro-production.up.railway.app"
          ? "railway"
          : "frontend";
      const routeCategory = url.pathname.startsWith("/api/")
        ? "api"
        : url.pathname.startsWith("/_next/")
          ? "next_internal"
          : url.pathname === "/sign-in" ||
              url.pathname.startsWith("/sign-in/")
            ? "sign_in"
            : url.pathname === "/sign-out" ||
                url.pathname.startsWith("/sign-out/")
              ? "sign_out"
              : url.pathname === "/projects"
                ? "projects_index"
                : url.pathname.startsWith("/projects/")
                  ? "projects_detail"
                  : "other_app";
      // Boolean only: the actual Next-Action header value is secret-ish.
      const nextAction = Boolean(request.headers()["next-action"]);
      const category = nonReadCategory(method, originCategory, routeCategory, nextAction);
      observedNonReadCategories.set(
        category,
        (observedNonReadCategories.get(category) ?? 0) + 1,
      );

      const allowedClerkSessionTransition =
        session !== 0 &&
        originCategory === "frontend" &&
        method === "POST" &&
        nextAction &&
        (url.pathname === "/sign-in" ||
          url.pathname === `/projects/${PROJECT_ID}/evidence`);
      if (allowedClerkSessionTransition) {
        const transition = `session${session}:${routeCategory}`;
        observedClerkTransitions.set(
          transition,
          (observedClerkTransitions.get(transition) ?? 0) + 1,
        );
        clerkTransitionRequests.push(request);
      } else {
        // Always fail closed for API writes, unrelated Next actions, unknown
        // target paths/methods, and requests during the anonymous/pacing phase.
        observedProductWriteRequests += 1;
      }
    }
  });

  await signInSyntheticProductionUser(page);
  const authorized = await assertRevisionPanel(page);
  const initialEvidenceFingerprint = evidenceFingerprint(
    authorized.protectedClauseText,
  );
  const provenApiOrigin = authorized.apiOrigin;

  await signOutThroughUi(page);
  session = 0;

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
    // The public Railway API is directly accessible; testing only the
    // same-origin frontend proxy could falsely pass due to Clerk middleware.
    // Keep its origin in the existing strict production API allowlist.
    const directBackendOrigin = requireProductionApiOrigin(
      "https://c2pro-production.up.railway.app",
    );
    for (const origin of new Set([
      provenApiOrigin,
      frontendOrigin,
      directBackendOrigin,
    ])) {
      if (origin !== frontendOrigin) requireProductionApiOrigin(origin);
      const isBackendOrigin =
        origin === directBackendOrigin ||
        (origin === provenApiOrigin && origin !== frontendOrigin);
      const revisionsPath = isBackendOrigin
        ? `/api/v1/documents/${DOCUMENT_ID}/revisions`
        : authorized.revisionPath;
      if (!revisionsPath.endsWith("/revisions")) {
        throw new Error("PQ939_AUTHENTICATED_REVISION_ROUTE_UNEXPECTED");
      }
      const entitiesPath = revisionsPath.replace(/\/revisions$/, "/entities");
      for (const [endpointKind, endpoint] of [
        ["revisions", revisionsPath],
        ["entities", entitiesPath],
        ["entities_a", `${entitiesPath}?revision_id=${REV_A_ID}`],
        ["entities_b", `${entitiesPath}?revision_id=${REV_B_ID}`],
      ] as const) {
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
        // Use the SAME bounded, nonsecret diagnostic for both an unexpected
        // status/redirect and a denial response that carries protected data.
        // Never include the URL, Location header, response body or clause text.
        const contentType = response.headers()["content-type"] ?? "";
        const isJsonResponse = /application\/json/i.test(contentType);
        const isHtmlResponse = /^text\/html(?:;|$)/i.test(contentType);
        const mimeClass = isJsonResponse ? "json" : isHtmlResponse ? "html" : "other";
        const diagnostic =
          `PQ939_ANONYMOUS_DENIAL_FAILED origin=${isBackendOrigin ? "railway" : "frontend"}` +
          ` route=${endpointKind} status=${status} mime=${mimeClass}`;
        expect(
          denied || loginRedirect,
          `${diagnostic} gates=not_denied`,
        ).toBe(true);

        // HTTP denial alone is NOT proof of confidentiality. Fail closed if
        // any known revision ID or in-memory synthetic clause content leaked
        // through an error response. Never log the body or clause strings.
        const deniedBytes = await response.body();
        const deniedBody = deniedBytes.toString("utf8");
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
        // An anonymous same-origin request to a route proven HTTP 200
        // when authenticated can be denied by Next.js with its generic HTML
        // 404 page BEFORE reaching the backend proxy. This is not a JSON API
        // error envelope. Accept ONLY an identifiable, bounded, generic 404
        // HTML page for the protected frontend route, with the size limit
        // enforced on actual response bytes, and keep protected
        // revision-ID/clause-fragment scans active for the entire HTML body.
        // Railway/direct-API denials MUST continue to use flat JSON envelopes.
        const genericFrontend404 =
          !isBackendOrigin &&
          origin === frontendOrigin &&
          status === 404 &&
          isHtmlResponse &&
          deniedBytes.length <= 65536 &&
          /^<!doctype html\b/i.test(deniedBody.trimStart().slice(0, 80)) &&
          /\b404\b/.test(deniedBody.slice(0, 16384)) &&
          /(?:not found|could not be found)/i.test(
            deniedBody.slice(0, 16384),
          );

        // Flat JSON error envelopes remain required for every other API
        // denial. Reject nested arrays/objects under "detail"; never print
        // any error response body or protected contract content.
        let structuredDataLeak = false;
        if (denied) {
          if (!isJsonResponse) {
            structuredDataLeak = !genericFrontend404;
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
                    ["detail", "error", "message", "reason_code"].includes(key) &&
                    typeof value === "string",
                );
            } catch {
              structuredDataLeak = true;
            }
          }
        }
        // Diagnose failure by origin, endpoint category, HTTP status and
        // boolean gates ONLY. Never log tokens, URLs, payload or clause text.
        const failedGates = [
          leakedIdentifier ? "revision_id_present" : null,
          leakedClause ? "clause_fragment_present" : null,
          structuredDataLeak ? "denial_envelope_unrecognized" : null,
        ].filter(Boolean);
        expect(
          failedGates.length,
          `${diagnostic} gates=${failedGates.join(",")}`,
        ).toBe(0);
      }
    }
  } finally {
    await anon.close();
  }

  // Production run #38776664922 proved all anonymous denials but triggered
  // the 20-requests/user/minute production limit on the second signed-in
  // A/B view (429 on revision-scoped entities). Respect the existing 60s
  // limiter window BETWEEN signed-in sessions; this is test pacing, not an
  // API retry, permission bypass, rate-limit configuration change, or
  // relaxation of the A9/B7 / HTTP 200 assertions below. Waiting more than
  // one full window also avoids depending on runner/server clock alignment.
  await page.waitForTimeout(61_000);

  session = 2;
  await signInSyntheticProductionUser(page);
  const secondAuthorized = await assertRevisionPanel(page);
  expect(secondAuthorized.apiOrigin).toBe(provenApiOrigin);
  expect(
    evidenceFingerprint(secondAuthorized.protectedClauseText) ===
      initialEvidenceFingerprint,
    "PQ939_REVISION_CONTENT_FINGERPRINT_CHANGED",
  ).toBe(true);
  await signOutThroughUi(page);
  session = 0;

  // Match exactly the four individually scoped authentication control-plane
  // actions actually observed in run #38801876319; new/extra action classes
  // cannot silently become exempt from the zero-product-write invariant.
  const expectedClerkTransitions = [
    "session1:sign_in", "session1:projects_detail",
    "session2:sign_in", "session2:projects_detail",
  ];
  const unexpectedAuthActions = [...observedClerkTransitions.entries()]
    .filter(([category, count]) =>
      !expectedClerkTransitions.includes(category) || count !== 1,
    ).map(([category]) => category);
  const absentAuthActions = expectedClerkTransitions.filter(
    (category) => observedClerkTransitions.get(category) !== 1,
  );
  expect(
    unexpectedAuthActions.length + absentAuthActions.length,
    "PQ939_CLERK_AUTH_BOUNDARY_UNVERIFIED",
  ).toBe(0);
  const clerkResponses = await Promise.all(
    clerkTransitionRequests.map(async (request) => {
      const response = await request.response();
      return !request.failure() &&
        response !== null &&
        response.status() >= 200 &&
        response.status() < 400;
    }),
  );
  expect(
    clerkResponses.filter((passed) => !passed).length,
    "PQ939_CLERK_AUTH_ACTION_FAILED",
  ).toBe(0);

  // Emit ONLY bounded and deterministic request categories on failure.
  // Each recorded non-read request still makes qualification FAIL; diagnostics
  // cannot turn a browser POST/server action into an authorized product write.
  const nonReadCategories = [...observedNonReadCategories.entries()]
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([category, count]) => `${category}:${count}`)
    .join(" | ");
  expect(
    observedProductWriteRequests,
    `Production QA emitted a product/API write request: categories=${nonReadCategories}`,
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
