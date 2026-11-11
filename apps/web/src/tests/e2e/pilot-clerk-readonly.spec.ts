/**
 * PILOT G1: READ-ONLY authenticated probe against the deployed Railway PILOT.
 * Login occurs only in transient local Next.js contexts with Clerk DEVELOPMENT
 * identities. The backend under test receives GET requests only; never HITL POST.
 * Ephemeral Clerk JWTs stay in this runner's memory and are never logged/artifacted.
 */
import { expect, test, type Browser, type Page } from "@playwright/test";
import { clerk, setupClerkTestingToken } from "@clerk/testing/playwright";

const PILOT_API = "https://projectgraph-api-pilot.up.railway.app";
const A_EMAIL = process.env.E2E_CLERK_USER_EMAIL?.trim() || "testuser@c2pro.com";
const B_EMAIL = (process.env.INTEGRAL_CLERK_DEV_B_EMAIL ?? "").trim();

interface AuthContext {
  page: Page;
  close: () => Promise<void>;
  token: string;
  tenant: string;
}

async function login(browser: Browser, emailAddress: string): Promise<AuthContext> {
  const context = await browser.newContext({
    baseURL: "http://localhost:3100",
    storageState: { cookies: [], origins: [] },
  });
  try {
    const page = await context.newPage();
    await setupClerkTestingToken({ page });
    await page.goto("/");
    await clerk.loaded({ page });
    await clerk.signIn({ page, emailAddress });
    await page.waitForFunction(
      () => Boolean(window.Clerk?.session && window.Clerk?.organization),
      undefined,
      { timeout: 60_000 },
    );
    const { token, tenant } = await page.evaluate(async () => ({
      token: (await window.Clerk?.session?.getToken()) ?? "",
      tenant: String(
        (window.Clerk?.organization?.publicMetadata as { tenant_id?: string } | undefined)?.tenant_id ?? "",
      ),
    }));
    expect(token.length, "Clerk bearer token must exist").toBeGreaterThan(50);
    expect(tenant.length, "Clerk Organization must expose a tenant").toBeGreaterThan(0);
    return { page, token, tenant, close: () => context.close() };
  } catch (error) {
    await context.close();
    throw error;
  }
}

async function readProjects(request: import("@playwright/test").APIRequestContext, bearer: string) {
  const response = await request.get(PILOT_API + "/api/v1/projects", {
    failOnStatusCode: false,
    headers: { Authorization: "Bearer " + bearer },
  });
  const status = response.status();
  const body: unknown = status === 200 ? await response.json().catch(() => null) : null;
  const candidate = Array.isArray(body)
    ? body
    : body && typeof body === "object"
      ? ("items" in body ? body.items : "projects" in body ? body.projects : null)
      : null;
  const ids = Array.isArray(candidate)
    ? candidate.map((x: unknown) => (
      x && typeof x === "object" && "id" in x && typeof x.id === "string" ? x.id : ""
    )).filter(Boolean)
    : [];
  return { status, ids };
}

test("Railway PILOT accepts distinct Clerk DEV A/B and denies foreign project reads", async ({ browser, request }) => {
  test.skip(process.env.C2PRO_PILOT_READONLY_PROBE !== "1", "Manual read-only PILOT G1 probe only");
  expect(process.env.PILOT_API_URL).toBe(PILOT_API);
  expect(B_EMAIL, "second independent Clerk DEV identity must be configured").not.toBe("");
  expect(A_EMAIL).not.toBe(B_EMAIL);

  const anonymous = await request.get(PILOT_API + "/api/v1/projects", { failOnStatusCode: false });
  expect(anonymous.status(), "anonymous requests to PILOT must be refused").toBe(401);

  let a: AuthContext | undefined;
  let b: AuthContext | undefined;
  try {
    a = await login(browser, A_EMAIL);
    b = await login(browser, B_EMAIL);
    expect(a.tenant, "test identities must belong to different organizations").not.toBe(b.tenant);

    // The only requests made to Railway are GETs with short-lived Clerk tokens.
    const projectsA = await readProjects(request, a.token);
    const projectsB = await readProjects(request, b.token);
    console.log("PILOT_G1_READONLY auth_A_status=" + projectsA.status +
      " auth_B_status=" + projectsB.status +
      " A_has_projects=" + (projectsA.ids.length > 0) +
      " B_has_projects=" + (projectsB.ids.length > 0));
    expect(projectsA.status, "Railway PILOT must accept Clerk DEV A").toBe(200);
    expect(projectsB.status, "Railway PILOT must accept Clerk DEV B").toBe(200);

    for (const [bearer, foreignId] of [
      [b.token, projectsA.ids[0]],
      [a.token, projectsB.ids[0]],
    ] as const) {
      if (!foreignId) continue;
      const response = await request.get(PILOT_API + "/api/v1/projects/" + encodeURIComponent(foreignId), {
        failOnStatusCode: false,
        headers: { Authorization: "Bearer " + bearer },
      });
      expect([401, 403, 404], "cross-tenant project read must be denied").toContain(response.status());
    }
    if (!projectsA.ids.length || !projectsB.ids.length) {
      console.log("PILOT_G1_CROSS_TENANT=PARTIAL: no pre-existing project in at least one test tenant; no seed created");
    } else {
      console.log("PILOT_G1_CROSS_TENANT=PASS: both directions denied without data mutation");
    }
  } finally {
    await b?.close();
    await a?.close();
  }
});
