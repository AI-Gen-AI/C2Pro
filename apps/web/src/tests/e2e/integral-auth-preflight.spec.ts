/**
 * TS-E2E-INTEGRAL-AUTH-001 — authentication preflight of the integral S1–S8 UAT.
 *
 * Runs BEFORE the scenario, against the same local backend, and answers one question: do the two real Clerk
 * Development identities authenticate end to end? Each one signs in live (the documented Clerk sign-in token), and
 * the page's own session token is presented to the local API, which can only accept it if it verified the JWT with
 * the Development instance's public JWKS (CLERK_JWKS_URL) and resolved the user to a tenant. Nothing is created,
 * changed or deleted: the only calls are GETs of the identity's own project list, plus the cross-tenant checks
 * that every identity may NOT read a tenant it does not belong to.
 *
 * It records pseudonyms and statuses only (never a token, a cookie, an email or a Clerk id).
 */
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";

import { expect, test } from "@playwright/test";

import { callApi } from "./support/integral/api";
import { clerkIdentity, pseudonym, signInTenantB } from "./support/integral/identity";
import { signInAsJourneyUser } from "./support/pj01/session";

const TENANT_B_EMAIL = process.env.INTEGRAL_CLERK_DEV_B_EMAIL ?? process.env.E2E_CLERK_TENANT_B_USER_EMAIL ?? "";
const RECEIPT = path.join(process.cwd(), "playwright-report", "integral-auth-preflight.json");
const EMPTY_SESSION = { cookies: [], origins: [] };

test.describe("TS-E2E-INTEGRAL-AUTH-001: both Clerk Development identities authenticate", () => {
  test.beforeEach(({ browserName }, testInfo) => {
    testInfo.skip(process.env.INTEGRAL_UAT !== "1", `set INTEGRAL_UAT=1 to run the integral UAT preflight (${browserName})`);
  });

  test("A and B reach the local API with a real Clerk JWT, in different tenants", async ({ browser, baseURL }) => {
    test.setTimeout(300_000);
    const base = baseURL ?? "http://localhost:3100";
    expect(TENANT_B_EMAIL, "identity B must be configured").not.toBe("");

    const contextA = await browser.newContext({ baseURL: base, storageState: EMPTY_SESSION });
    const pageA = await contextA.newPage();
    await signInAsJourneyUser(pageA, base);
    const identityA = await clerkIdentity(pageA);
    const listA = await callApi(pageA, "/api/v1/projects");

    const tenantB = await signInTenantB(browser, base, TENANT_B_EMAIL);
    const identityB = await clerkIdentity(tenantB.page);
    const listB = await callApi(tenantB.page, "/api/v1/projects");

    const receipt = {
      schema: "c2pro-integral-auth-preflight/v1",
      a: { user: pseudonym(identityA.userId), organization: pseudonym(identityA.organizationId), tenant: identityA.tenantId, projectsListStatus: listA.status },
      b: { user: pseudonym(identityB.userId), organization: pseudonym(identityB.organizationId), tenant: identityB.tenantId, projectsListStatus: listB.status },
      distinctUsers: identityA.userId !== identityB.userId,
      distinctOrganizations: identityA.organizationId !== identityB.organizationId,
      distinctTenants: identityA.tenantId !== identityB.tenantId,
    };
    mkdirSync(path.dirname(RECEIPT), { recursive: true });
    writeFileSync(RECEIPT, `${JSON.stringify(receipt, null, 2)}\n`, "utf8");
    await tenantB.close();
    await contextA.close();

    expect(listA.status, "identity A's JWT is accepted by the local API (JWKS verified)").toBe(200);
    expect(listB.status, "identity B's JWT is accepted by the local API (JWKS verified)").toBe(200);
    expect(receipt.distinctUsers, "A and B are different users").toBe(true);
    expect(receipt.distinctOrganizations, "A and B are in different Organizations").toBe(true);
    expect(receipt.distinctTenants, "A and B resolve to different tenants").toBe(true);
  });
});
