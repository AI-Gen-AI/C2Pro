/**
 * ACC-01 S1: bounded, READ-ONLY Clerk Production identity/isolation check.
 *
 * This does NOT run the development-only Clerk provisioner, create projects,
 * modify Clerk users/orgs, or inspect customer-owned projects. The sole
 * allowed target is the pre-existing synthetic #939 project already qualified
 * in 939-production-revision-readonly.spec.ts.
 *
 * A real Clerk session is obtained via the production testing helper.
 * This is NOT proof of a human typing a password into the sign-in UI.
 * A->B also remains NOT_RUN until B has a separately authorized synthetic project.
 */
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";

import { clerk } from "@clerk/testing/playwright";
import { expect, test, type Page } from "@playwright/test";

import { requireProductionApiOrigin, requireProductionOrigin } from "./support/prod-preflight";

const TENANT_B_ID = "00000000-0000-0000-0000-00000000a1f1";
const APPROVED_A_PROJECT_ID = "e7c6031f-cd9e-4642-a5ea-35a0207ceaeb";
const OUTPUT = path.join(process.cwd(), "playwright", ".prod-acceptance", "s1-b-to-a-readonly.json");

function required(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error("S1_READONLY_MISSING_ENV:" + name);
  return value;
}

function assertPreflight(): void {
  if (process.env.PROD_S1_CONFIRM_READONLY !== "RUN-S1-READONLY") {
    throw new Error("S1_READONLY_NOT_EXPLICITLY_AUTHORIZED");
  }
  requireProductionOrigin(required("PLAYWRIGHT_BASE_URL"));
  if (!required("CLERK_SECRET_KEY").startsWith("sk_live_")) {
    throw new Error("S1_READONLY_REQUIRES_PRODUCTION_CLERK_KEY");
  }
  if (!required("CLERK_PUBLISHABLE_KEY").startsWith("pk_live_")) {
    throw new Error("S1_READONLY_REQUIRES_PRODUCTION_CLERK_PUBLISHABLE_KEY");
  }
  if (required("PROD_ACCEPTANCE_EXPECTED_TENANT_ID") === TENANT_B_ID) {
    throw new Error("S1_READONLY_TENANTS_NOT_DISTINCT");
  }
  required("PROD_ACCEPTANCE_CLERK_ORGANIZATION_ID");
  required("PROD_ACCEPTANCE_CLERK_EMAIL");
  required("E2E_CLERK_TENANT_B_USER_EMAIL");
}

type BrowserOrg = {
  sessionActive: boolean;
  activeOrgId: string | null;
  tenantId: string | null;
  memberships: number;
};

async function startClerkSession(page: Page, email: string, expectedTenant: string): Promise<BrowserOrg> {
  await page.goto("/");
  await clerk.signIn({ page, emailAddress: email });
  await page.goto("/projects");
  await expect(page.getByRole("heading", { name: /projects/i })).toBeVisible({ timeout: 30_000 });
  await page.waitForFunction(
    (tenant: string) =>
      window.Clerk?.session?.status === "active" &&
      window.Clerk?.organization?.publicMetadata?.tenant_id === tenant,
    expectedTenant,
    { timeout: 60_000 },
  );
  return page.evaluate<BrowserOrg>(() => ({
    sessionActive: window.Clerk?.session?.status === "active",
    activeOrgId: window.Clerk?.organization?.id ?? null,
    tenantId:
      typeof window.Clerk?.organization?.publicMetadata?.tenant_id === "string"
        ? window.Clerk.organization.publicMetadata.tenant_id
        : null,
    memberships: window.Clerk?.user?.organizationMemberships?.length ?? 0,
  }));
}

function watchProjectReads(page: Page): number[] {
  const statuses: number[] = [];
  page.on("response", (response) => {
    const url = new URL(response.url());
    const current = requireProductionOrigin(page.url());
    let originAllowed = url.origin === current;
    if (!originAllowed) {
      try {
        originAllowed = requireProductionApiOrigin(url.origin) === url.origin;
      } catch {
        originAllowed = false;
      }
    }
    if (
      originAllowed &&
      url.pathname.startsWith("/api/") &&
      url.pathname.includes("/projects/" + APPROVED_A_PROJECT_ID) &&
      response.request().method() === "GET"
    ) {
      statuses.push(response.status());
    }
  });
  return statuses;
}

test.describe("ACC-01 S1 production Clerk identities (read-only)", () => {
  test.describe.configure({ mode: "serial", timeout: 180_000 });

  test.beforeAll(() => assertPreflight());

  test("A has real Clerk session and can read approved synthetic A project", async ({ browser, baseURL }) => {
    const context = await browser.newContext({ baseURL, storageState: { cookies: [], origins: [] } });
    try {
      const page = await context.newPage();
      const facts = await startClerkSession(page, required("PROD_ACCEPTANCE_CLERK_EMAIL"), required("PROD_ACCEPTANCE_EXPECTED_TENANT_ID"));
      expect(facts.sessionActive).toBe(true);
      expect(facts.tenantId).toBe(required("PROD_ACCEPTANCE_EXPECTED_TENANT_ID"));
      expect(facts.activeOrgId).toBe(required("PROD_ACCEPTANCE_CLERK_ORGANIZATION_ID"));
      const statuses = watchProjectReads(page);
      await page.goto("/projects/" + APPROVED_A_PROJECT_ID + "/documents");
      await expect.poll(() => statuses.length, { timeout: 30_000 }).toBeGreaterThan(0);
      expect(statuses, "the approved A project must be accessible to A").toContain(200);
    } finally {
      await context.close();
    }
  });

  test("B has a distinct real Clerk org and is denied the same A project", async ({ browser, baseURL }) => {
    const context = await browser.newContext({ baseURL, storageState: { cookies: [], origins: [] } });
    try {
      const page = await context.newPage();
      const facts = await startClerkSession(page, required("E2E_CLERK_TENANT_B_USER_EMAIL"), TENANT_B_ID);
      expect(facts.sessionActive).toBe(true);
      expect(facts.memberships).toBe(1);
      expect(facts.tenantId).toBe(TENANT_B_ID);
      expect(facts.activeOrgId).toBeTruthy();
      expect(facts.activeOrgId).not.toBe(required("PROD_ACCEPTANCE_CLERK_ORGANIZATION_ID"));

      const statuses = watchProjectReads(page);
      await page.goto("/projects/" + APPROVED_A_PROJECT_ID + "/documents");
      await expect.poll(() => statuses.length, { timeout: 30_000 }).toBeGreaterThan(0);
      expect(statuses.every((status) => [401, 403, 404].includes(status))).toBe(true);
      expect(statuses).not.toContain(429);

      mkdirSync(path.dirname(OUTPUT), { recursive: true });
      writeFileSync(
        OUTPUT,
        JSON.stringify({
          case: "ACC-01-S1-CLERK-PRODUCTION-READONLY",
          user_a_synthetic_project_read: "PASS_FROM_PRIOR_TEST",
          tenant_b_clerk_session: "PASS",
          tenant_b_org_metadata: "PASS",
          tenant_b_to_a_denial: "PASS",
          tenant_a_to_b_denial: "NOT_RUN_NO_AUTHORIZED_B_PROJECT",
          ui_password_login: "NOT_RUN_TESTING_TOKEN_AUTH",
          database_isolated_uat: "NOT_RUN_DEPLOYED_READONLY",
        }, null, 2),
      );
    } finally {
      await context.close();
    }
  });
});
