/**
 * Shared authenticated storageState for the E2E specs that restore one.
 *
 * Uses the flow the INSTALLED @clerk/testing (2.2.7) documents for automated
 * sign-in: `clerk.signIn({ page, emailAddress })` resolves the configured E2E
 * identity through the Clerk Backend API, mints a short-lived sign-in token and
 * consumes it with the `ticket` strategy.
 *
 * That replaces the previous password-first-factor flow, which required a
 * password literal in this file. There is no credential here now, and no
 * hand-rolled JWT decoding: identity comes from Clerk's typed client resources.
 *
 * The canonical P0b journey deliberately does NOT restore this file — it signs
 * in live in its own context, because serialize/restore is one of the variables
 * under investigation. This setup remains for the specs that do rely on it.
 */

import { expect, test as setup } from "@playwright/test";

import { AUTH_STATE_FILE, clerkFacts, establishAuthenticatedSession } from "./support/p0b-auth";

/** Optional pin for the configured E2E identity. Reused, never replaced. */
const expectedUserId = process.env.E2E_CLERK_USER_ID ?? null;

setup("authenticate", async ({ page }) => {
  await establishAuthenticatedSession(page);

  const facts = await clerkFacts(page);
  expect(facts.clerkSessionActive, "storageState must be saved from an active session").toBe(true);
  expect(facts.expectedOrganizationActive, "storageState must carry an active Organization").toBe(
    true,
  );

  if (expectedUserId) {
    const userId = await page.evaluate(() => window.Clerk?.user?.id ?? null);
    expect(userId, "signed-in identity must be the configured E2E user").toBe(expectedUserId);
  }

  await page.context().storageState({ path: AUTH_STATE_FILE });
});
