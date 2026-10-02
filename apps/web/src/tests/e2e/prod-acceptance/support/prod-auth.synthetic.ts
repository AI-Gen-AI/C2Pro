import { expect, type Page, type Request } from "@playwright/test";

import {
  assertProductionJourneyPreflight,
  requireProductionOrigin,
  type BrowserIdentityFacts,
} from "./prod-preflight";

const API_PATH = /\/api(?:\/v1)?\//;

interface ObservedApplicationAuth {
  tenantId: string | null;
  bearerObserved: boolean;
}

function productionBaseUrl(): string {
  return process.env.PROD_ACCEPTANCE_BASE_URL ?? "https://c2pro.io";
}

function credentials(): { email: string; password: string } {
  const email = process.env.PROD_ACCEPTANCE_CLERK_EMAIL;
  const password = process.env.PROD_ACCEPTANCE_CLERK_PASSWORD;
  if (!email || !password) {
    throw new Error(
      "PROD_ACCEPTANCE_MISSING_ENV:PROD_ACCEPTANCE_CLERK_EMAIL,PROD_ACCEPTANCE_CLERK_PASSWORD",
    );
  }
  return { email, password };
}

function observeApplicationAuth(
  page: Page,
  baseOrigin: string,
): {
  facts: () => ObservedApplicationAuth;
} {
  let tenantId: string | null = null;
  let bearerObserved = false;

  page.on("request", (request: Request) => {
    const url = new URL(request.url());
    if (url.origin !== baseOrigin || !API_PATH.test(url.pathname)) return;
    const headers = request.headers();
    bearerObserved ||= Boolean(headers.authorization);
    tenantId ??= headers["x-tenant-id"] ?? null;
  });

  return {
    facts: () => ({ tenantId, bearerObserved }),
  };
}

async function activeOrganizationId(page: Page): Promise<string | null> {
  return page.evaluate(() => window.Clerk?.organization?.id ?? null);
}

type SafeClerkDiagnostics = {
  pathname: string;
  sessionStatus: string | null;
  hasUser: boolean;
  hasOrganization: boolean;
};

async function safeClerkDiagnostics(page: Page): Promise<SafeClerkDiagnostics> {
  return page.evaluate(() => ({
    pathname: window.location.pathname,
    sessionStatus: window.Clerk?.session?.status ?? null,
    hasUser: Boolean(window.Clerk?.user),
    hasOrganization: Boolean(window.Clerk?.organization),
  }));
}

async function waitForSignedInClerkUser(page: Page): Promise<void> {
  try {
    await page.waitForFunction(
      () =>
        window.Clerk?.session?.status === "active" &&
        Boolean(window.Clerk?.user),
      undefined,
      { timeout: 60_000 },
    );
  } catch {
    const facts = await safeClerkDiagnostics(page);
    throw new Error(
      "PROD_ACCEPTANCE_CLERK_SESSION_NOT_ACTIVE:" +
        JSON.stringify(facts),
    );
  }
}

async function waitForActiveOrganization(page: Page): Promise<void> {
  try {
    await page.waitForFunction(
      () => Boolean(window.Clerk?.organization),
      undefined,
      { timeout: 60_000 },
    );
  } catch {
    const facts = await safeClerkDiagnostics(page);
    throw new Error(
      "PROD_ACCEPTANCE_CLERK_ORGANIZATION_NOT_ACTIVE:" +
        JSON.stringify(facts),
    );
  }
}

export async function signInSyntheticProductionUser(
  page: Page,
): Promise<BrowserIdentityFacts> {
  const baseOrigin = requireProductionOrigin(productionBaseUrl());
  const { email, password } = credentials();
  const observed = observeApplicationAuth(page, baseOrigin);

  await page.goto(`${baseOrigin}/sign-in`);
  const identifier = page.locator('input[name="identifier"]');
  await expect(identifier).toBeVisible({ timeout: 30_000 });
  await identifier.fill(email);

  await page.getByRole("button", { name: /^continue$/i }).click();
  const passwordInput = page.locator('input[name="password"]');
  await expect(passwordInput).toBeVisible({ timeout: 30_000 });
  await passwordInput.fill(password);
  await page.getByRole("button", { name: /^continue$/i }).click();

  // AUTH is proven by the real Clerk production session, not by whether the
  // SignIn component happens to complete its forceRedirectUrl navigation.
  // Once the session exists, enter the protected app explicitly so AuthSync can
  // activate the user's sole Organization and emit the application tenant.
  await waitForSignedInClerkUser(page);
  if (!/\/projects(?:\?|$|\/)/.test(new URL(page.url()).pathname)) {
    await page.goto(`${baseOrigin}/projects`);
  }
  await waitForActiveOrganization(page);

  // Force one ordinary product read so the exact application tenant header is
  // observed from AuthSync/Zustand, not inferred from a JWT or copied secret.
  await page.goto(`${baseOrigin}/projects`);
  await expect(page.getByRole("heading", { name: /projects/i })).toBeVisible({
    timeout: 30_000,
  });
  await expect
    .poll(() => observed.facts().bearerObserved, { timeout: 30_000 })
    .toBe(true);
  await expect
    .poll(() => observed.facts().tenantId, { timeout: 30_000 })
    .not.toBeNull();

  const facts: BrowserIdentityFacts = {
    activeTenantId: observed.facts().tenantId,
    activeOrganizationId: await activeOrganizationId(page),
  };

  if (process.env.PROD_ACCEPTANCE_TENANT_PREFLIGHT_VERIFIED !== "1") {
    throw new Error(
      "PROD_ACCEPTANCE_PREFLIGHT_FAILED:TENANT_NOT_MARKED_SYNTHETIC",
    );
  }
  assertProductionJourneyPreflight(facts, true);
  return facts;
}

export async function signOutThroughUi(page: Page): Promise<void> {
  const userButton = page.getByRole("button", { name: /open user button/i });
  await expect(userButton).toBeVisible({ timeout: 30_000 });
  await userButton.click();
  const signOut = page.getByRole("menuitem", { name: /sign out/i });
  await expect(signOut).toBeVisible({ timeout: 15_000 });
  await signOut.click();
  await page.waitForURL(/\/sign-in/, { timeout: 30_000 });
}
