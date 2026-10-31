/**
 * Identities of the integral S1-S8 UAT in the browser: who is signed in (Clerk), the second tenant's own
 * context, and what the application answers about a project of ANOTHER tenant. Shared by the scenario and by the
 * authentication preflight so both judge the same thing in the same way.
 */
import { clerk, setupClerkTestingToken } from "@clerk/testing/playwright";
import type { Browser, Page } from "@playwright/test";

import { callApi } from "./api";
import { sha256Hex } from "./ledger";

const EMPTY_SESSION = { cookies: [], origins: [] };

export interface ClerkIdentity {
  userId: string;
  organizationId: string;
  tenantId: string;
}

export async function clerkIdentity(page: Page): Promise<ClerkIdentity> {
  return page.evaluate(() => ({
    userId: window.Clerk?.user?.id ?? "",
    organizationId: window.Clerk?.organization?.id ?? "",
    tenantId: String((window.Clerk?.organization?.publicMetadata as { tenant_id?: string } | undefined)?.tenant_id ?? ""),
  }));
}

export const pseudonym = (value: string): string => (value ? sha256Hex(value).slice(0, 12) : "");

/** A second, independently authenticated Clerk identity in its own context (live sign-in token, empty storage). */
export async function signInTenantB(browser: Browser, baseURL: string, emailAddress: string): Promise<{ page: Page; close: () => Promise<void> }> {
  const context = await browser.newContext({ baseURL, storageState: EMPTY_SESSION });
  const page = await context.newPage();
  await setupClerkTestingToken({ page });
  await page.goto("/");
  await clerk.loaded({ page });
  await clerk.signIn({ page, emailAddress });
  await page.waitForFunction(() => Boolean(window.Clerk?.organization), undefined, { timeout: 60_000 });
  return { page, close: () => context.close() };
}

export const DENIAL = [401, 403, 404];

/** What the application answers a signed-in user about a project of ANOTHER tenant: only denials are acceptable. */
export async function denialsFor(page: Page, foreignProjectId: string): Promise<number[]> {
  const urls = [
    `/api/v1/projects/${foreignProjectId}`,
    `/api/v1/projects/${foreignProjectId}/documents`,
    `/api/v1/alerts/projects/${foreignProjectId}`,
    `/api/v1/projects/${foreignProjectId}/health`,
  ];
  const statuses: number[] = [];
  for (const url of urls) statuses.push((await callApi(page, url)).status);
  return statuses;
}

