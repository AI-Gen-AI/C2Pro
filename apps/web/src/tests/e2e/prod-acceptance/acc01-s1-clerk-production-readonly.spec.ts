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

/**
 * Server-side positive identity control. GET /api/auth/me is backed by
 * AuthService.get_current_user() and the persisted tenant association. Merely
 * observing a Clerk session or copying publicMetadata is NOT sufficient.
 * Never return or log the bearer, user identity, or the full API response.
 */
async function verifyAuthenticatedBackendTenant(page: Page, expectedTenantId: string): Promise<void> {
  const evidence = await page.evaluate(async (tenantId: string) => {
    const client = window.Clerk;
    const session = client?.session;
    const organization = client?.organization;
    if (session?.status !== "active" || !organization) {
      return { status: 0, tenantMatches: false, activeUser: false };
    }
    // Compare the active organization before requesting its scoped token.
    if (organization.publicMetadata?.tenant_id !== tenantId) {
      return { status: 0, tenantMatches: false, activeUser: false };
    }

    let token: string | null;
    try {
      token = await session.getToken({
        organizationId: organization.id,
        skipCache: true,
      });
    } catch {
      return { status: 0, tenantMatches: false, activeUser: false };
    }
    if (!token) return { status: 0, tenantMatches: false, activeUser: false };

    try {
      const response = await fetch("/api/auth/me", {
        method: "GET",
        cache: "no-store",
        credentials: "same-origin",
        headers: {
          Authorization: `Bearer ${token}`,
          "X-Tenant-ID": tenantId,
        },
      });
      if (response.status !== 200) {
        return { status: response.status, tenantMatches: false, activeUser: false };
      }
      const payload: unknown = await response.json();
      const shape = payload as {
        tenant?: { id?: unknown };
        user?: { is_active?: unknown };
      } | null;
      return {
        status: response.status,
        tenantMatches: shape?.tenant?.id === tenantId,
        activeUser: shape?.user?.is_active === true,
      };
    } catch {
      return { status: 0, tenantMatches: false, activeUser: false };
    }
  }, expectedTenantId);

  expect(evidence.status, "the backend must authenticate this Clerk identity via GET /auth/me").toBe(200);
  expect(evidence.tenantMatches, "the backend's persisted tenant must match Clerk's active organization").toBe(true);
  expect(evidence.activeUser, "backend user must be active").toBe(true);
}

/**
 * Compare both identities using the SAME exact tenant-scoped backend route.
 * A status 200 on some other project endpoint must not prove that A owns this
 * synthetic project; B's neutral 404 must come from this exact route.
 * Project data and bearer token remain within the browser, never in artifacts.
 */
async function readBoundedSyntheticProject(
  page: Page,
  expectedTenantId: string,
): Promise<{ status: number; projectOwned: boolean }> {
  return page.evaluate(async ({ tenantId, projectId }) => {
    const session = window.Clerk?.session;
    const org = window.Clerk?.organization;
    if (session?.status !== "active" || !org || org.publicMetadata?.tenant_id !== tenantId) {
      return { status: 0, projectOwned: false };
    }

    let token: string | null;
    try {
      token = await session.getToken({ organizationId: org.id, skipCache: true });
    } catch {
      return { status: 0, projectOwned: false };
    }
    if (!token) return { status: 0, projectOwned: false };

    try {
      const response = await fetch("/api/projects/" + projectId, {
        method: "GET",
        cache: "no-store",
        credentials: "same-origin",
        headers: {
          Authorization: \`Bearer \${token}\`,
          "X-Tenant-ID": tenantId,
        },
      });
      if (response.status !== 200) {
        return { status: response.status, projectOwned: false };
      }
      const payload: unknown = await response.json();
      const project = payload as { id?: unknown; tenant_id?: unknown } | null;
      return {
        status: response.status,
        projectOwned: project?.id === projectId && project?.tenant_id === tenantId,
      };
    } catch {
      return { status: 0, projectOwned: false };
    }
  }, { tenantId: expectedTenantId, projectId: APPROVED_A_PROJECT_ID });
}

/**
 * Refuse application writes even if an unexpected component tries to emit one
 * while the browser signs in or renders the synthetic project. Clerk's own
 * cross-origin authentication calls are outside this product-write boundary.
 */
async function preventProductWrites(page: Page): Promise<() => void> {
  let refused = 0;
  await page.route("**/*", async (route) => {
    const request = route.request();
    const method = request.method().toUpperCase();
    if (["GET", "HEAD", "OPTIONS"].includes(method)) {
      await route.continue();
      return;
    }
    let isProductOrigin: boolean;
    try {
      const url = new URL(request.url());
      isProductOrigin =
        url.protocol === "https:" &&
        ["c2pro.io", "www.c2pro.io", "c2pro-production.up.railway.app"].includes(url.hostname);
    } catch {
      refused += 1;
      await route.abort();
      return;
    }
    if (isProductOrigin) {
      refused += 1;
      await route.abort();
      return;
    }
    await route.continue();
  });
  return () => expect(refused, "read-only S1 must not attempt application writes").toBe(0);
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
      const verifyReadOnly = await preventProductWrites(page);
      const facts = await startClerkSession(page, required("PROD_ACCEPTANCE_CLERK_EMAIL"), required("PROD_ACCEPTANCE_EXPECTED_TENANT_ID"));
      expect(facts.sessionActive).toBe(true);
      expect(facts.tenantId).toBe(required("PROD_ACCEPTANCE_EXPECTED_TENANT_ID"));
      expect(facts.activeOrgId).toBe(required("PROD_ACCEPTANCE_CLERK_ORGANIZATION_ID"));
      await verifyAuthenticatedBackendTenant(page, required("PROD_ACCEPTANCE_EXPECTED_TENANT_ID"));
      const exactProject = await readBoundedSyntheticProject(page, required("PROD_ACCEPTANCE_EXPECTED_TENANT_ID"));
      expect(exactProject.status, "A must GET the exact authorized synthetic project").toBe(200);
      expect(exactProject.projectOwned, "backend must return exact project ID and A tenant").toBe(true);
      const statuses = watchProjectReads(page);
      await page.goto("/projects/" + APPROVED_A_PROJECT_ID + "/documents");
      await expect.poll(() => statuses.length, { timeout: 30_000 }).toBeGreaterThan(0);
      expect(statuses, "the approved A project must be accessible to A").toContain(200);
      verifyReadOnly();
    } finally {
      await context.close();
    }
  });

  test("B has a distinct real Clerk org and is denied the same A project", async ({ browser, baseURL }) => {
    const context = await browser.newContext({ baseURL, storageState: { cookies: [], origins: [] } });
    try {
      const page = await context.newPage();
      const verifyReadOnly = await preventProductWrites(page);
      const facts = await startClerkSession(page, required("E2E_CLERK_TENANT_B_USER_EMAIL"), TENANT_B_ID);
      expect(facts.sessionActive).toBe(true);
      expect(facts.memberships).toBe(1);
      expect(facts.tenantId).toBe(TENANT_B_ID);
      expect(facts.activeOrgId).toBeTruthy();
      expect(facts.activeOrgId).not.toBe(required("PROD_ACCEPTANCE_CLERK_ORGANIZATION_ID"));

      // Fail closed if B exists in Clerk but is not linked to a real backend user
      // in its own tenant. Otherwise an unauthenticated 401 could appear to pass.
      await verifyAuthenticatedBackendTenant(page, TENANT_B_ID);

      const exactProject = await readBoundedSyntheticProject(page, TENANT_B_ID);
      expect(exactProject.status, "B must see neutral 404 for A's exact synthetic project").toBe(404);
      expect(exactProject.projectOwned).toBe(false);

      const statuses = watchProjectReads(page);
      await page.goto("/projects/" + APPROVED_A_PROJECT_ID + "/documents");
      await expect.poll(() => statuses.length, { timeout: 30_000 }).toBeGreaterThan(0);
      expect(
        statuses.every((status) => [403, 404].includes(status)),
        "B was already authenticated by /auth/me; target must deny, not return 401/429",
      ).toBe(true);
      expect(statuses).not.toContain(401);
      expect(statuses).not.toContain(429);
      verifyReadOnly();

      mkdirSync(path.dirname(OUTPUT), { recursive: true });
      writeFileSync(
        OUTPUT,
        JSON.stringify({
          case: "ACC-01-S1-CLERK-PRODUCTION-READONLY",
          user_a_synthetic_project_read: "PASS_FROM_PRIOR_TEST",
          tenant_b_clerk_session: "PASS",
          tenant_b_org_metadata: "PASS",
          tenant_b_backend_authenticated_and_tenant_linked: "PASS",
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
