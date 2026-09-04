/**
 * TS-E2E-AUTH-CONTINUITY-001 — cheap standalone diagnostic. NOT the authority.
 *
 * Separate Playwright tests get separate browser contexts, so a green run here
 * cannot license the canonical journey. The acceptance authority is
 * assertProjectEntryContinuity() called INSIDE
 * p0b-single-document-health.spec.ts, in that test's own page and context.
 *
 * This spec exists only to reproduce the same seam cheaply when investigating,
 * using the identical helpers, so a hypothesis can be checked in ~30s without
 * running the full journey. Treat its result as an indication, never as proof
 * about the journey.
 */

import { test } from "@playwright/test";

import {
  assertProjectEntryContinuity,
  establishAuthenticatedSession,
  observeAuth,
} from "./support/p0b-auth";

test.describe("TS-E2E-AUTH-CONTINUITY-001: project-entry seam (diagnostic only)", () => {
  test.describe.configure({ timeout: 120_000 });

  test("session survives project entry", async ({ baseURL, page }) => {
    const observation = observeAuth(page, baseURL ?? "http://localhost:3100");
    await establishAuthenticatedSession(page, observation);
    await assertProjectEntryContinuity(page, observation);
  });
});
