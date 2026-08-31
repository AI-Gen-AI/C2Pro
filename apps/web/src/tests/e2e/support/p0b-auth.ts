/**
 * The canonical P0b authentication preamble, in ONE place.
 *
 * The journey's auth kept failing and every diagnostic I wrote drifted from it,
 * so the diagnostic proved nothing about the journey. This module is the fix:
 * the bounded project-entry gate and the six-minute journey import the same
 * function and therefore execute byte-for-byte the same sequence, in the same
 * page and the same context.
 *
 * Sequence (no sign-in): the chromium project already restores the storageState
 * that auth.setup produced, so the session exists before this runs. It needs
 * only the testing token, which the Clerk development instance requires before
 * it will honour a restored session.
 *
 *   restored storageState -> setupClerkTestingToken -> / -> Clerk.loaded
 *   -> session present/subject -> /projects -> Projects visible
 *
 * DIAGNOSTICS ARE STRUCTURAL ONLY. Cookie names, domains, paths and flags are
 * reported; values never are. Session presence and subject are reported; tokens,
 * testing tokens and passwords never are. A failing auth test must not become a
 * credential disclosure.
 */

import { readFileSync } from "node:fs";
import path from "node:path";

import { setupClerkTestingToken } from "@clerk/testing/playwright";
import { expect, type BrowserContext, type Page } from "@playwright/test";

const STORAGE_STATE = path.join(process.cwd(), "playwright", ".auth", "user.json");

/** Cookie identity WITHOUT its value. */
export interface CookieShape {
  name: string;
  domain: string;
  cookiePath: string;
  httpOnly: boolean;
  secure: boolean;
  sameSite: string;
}

interface RawCookie {
  name: string;
  domain: string;
  path: string;
  httpOnly?: boolean;
  secure?: boolean;
  sameSite?: string;
}

function shape(cookie: RawCookie): CookieShape {
  return {
    name: cookie.name,
    domain: cookie.domain,
    cookiePath: cookie.path,
    httpOnly: Boolean(cookie.httpOnly),
    secure: Boolean(cookie.secure),
    sameSite: cookie.sameSite ?? "unset",
  };
}

function sortByName(cookies: CookieShape[]): CookieShape[] {
  return [...cookies].sort((a, b) => a.name.localeCompare(b.name));
}

/** Cookie shapes auth.setup serialized, read straight from storageState. */
export function storedCookieShapes(): CookieShape[] {
  try {
    const raw = JSON.parse(readFileSync(STORAGE_STATE, "utf8")) as { cookies?: RawCookie[] };
    return sortByName((raw.cookies ?? []).map(shape));
  } catch {
    return [];
  }
}

export async function restoredCookieShapes(context: BrowserContext): Promise<CookieShape[]> {
  return sortByName((await context.cookies()).map(shape));
}

/** Session presence and subject only — never the token itself. */
export async function sessionFacts(
  page: Page,
): Promise<{ present: boolean; subject: unknown }> {
  return page
    .evaluate(async () => {
      const clerk = window.Clerk;
      if (!clerk?.session) return { present: false, subject: null };
      const token = await clerk.session.getToken();
      if (!token) return { present: true, subject: null };
      const payload = token.split(".")[1];
      if (!payload) return { present: true, subject: null };
      const normalized = payload.replace(/-/g, "+").replace(/_/g, "/");
      return {
        present: true,
        subject: (JSON.parse(atob(normalized)) as { sub?: unknown }).sub ?? null,
      };
    })
    .catch(() => ({ present: false, subject: null }));
}

export interface DocumentHop {
  url: string;
  status: number;
  at: number;
}

/**
 * Record document-level responses only — the redirect chain the middleware
 * actually drives, with timings so a redirect can be placed relative to a click.
 */
export function recordDocumentChain(page: Page): DocumentHop[] {
  const chain: DocumentHop[] = [];
  page.on("response", (response) => {
    if (response.request().resourceType() === "document") {
      chain.push({ url: response.url(), status: response.status(), at: Date.now() });
    }
  });
  return chain;
}

/** A safe, structural snapshot of auth state at one point in the flow. */
export async function authSnapshot(
  label: string,
  page: Page,
  context: BrowserContext,
): Promise<Record<string, unknown>> {
  const facts = await sessionFacts(page);
  const restored = await restoredCookieShapes(context);
  const stored = storedCookieShapes();
  return {
    label,
    at: Date.now(),
    url: page.url(),
    clerkSessionPresent: facts.present,
    clerkSubject: facts.subject,
    restoredCookies: restored,
    storedButNotRestored: stored
      .filter((s) => !restored.some((r) => r.name === s.name && r.domain === s.domain))
      .map((c) => c.name),
    restoredButNotStored: restored
      .filter((r) => !stored.some((s) => s.name === r.name && s.domain === r.domain))
      .map((c) => c.name),
  };
}

/**
 * The canonical preamble. Used identically by the project-entry gate and by the
 * full journey, so a green gate genuinely says something about the journey.
 */
export async function establishAuthenticatedSession(page: Page): Promise<void> {
  await setupClerkTestingToken({ page });
  await page.goto("/");
  await page.waitForFunction(() => window.Clerk?.loaded === true);

  const facts = await sessionFacts(page);
  expect(
    facts.present,
    "storageState from auth.setup must restore a live Clerk session",
  ).toBe(true);

  await page.goto("/projects");
  await expect(page.locator('h1:has-text("Projects")')).toBeVisible({ timeout: 30_000 });
}
