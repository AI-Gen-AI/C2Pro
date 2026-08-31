/**
 * TS-E2E-AUTH-CONTINUITY-001 — does the canonical session survive project entry?
 *
 * A previous version of this gate ran `testing token -> /projects` and passed,
 * while the journey kept failing. That proved nothing: it was a second Playwright
 * invocation, a second setup/storageState/chromium execution, and a shorter
 * sequence than the journey's real preamble. A gate that does not reproduce the
 * thing it guards is not evidence.
 *
 * This version imports establishAuthenticatedSession from support/p0b-auth, the
 * SAME function the journey uses, so the preamble is byte-for-byte identical and
 * runs in the same page and context. It then advances exactly one step further —
 * to the transition the evidence points at:
 *
 *   ... -> /projects -> Projects visible -> New Project click
 *   -> project-name-input interactable
 *
 * The journey's last failure showed the input RESOLVING and then the app
 * redirecting to /sign-in 58 times, so the loss happens at or just after that
 * click. This races the two outcomes on a short bound (~20s) instead of burning
 * the journey's 360s timeout, and captures structural state at three points so
 * we can tell whether the session deteriorates BEFORE the click, whether the
 * CLICK causes it, or whether a background/middleware refresh invalidates it.
 *
 * Never emits cookie values, JWTs, testing tokens, passwords or any other secret
 * material.
 */

import { expect, test } from "@playwright/test";

import {
  authSnapshot,
  establishAuthenticatedSession,
  recordDocumentChain,
} from "./support/p0b-auth";

/** Short by design: this answers in seconds, not in journey minutes. */
const ENTRY_RACE_MS = 20_000;

test.describe("TS-E2E-AUTH-CONTINUITY-001: session survives project entry", () => {
  test.describe.configure({ timeout: 120_000 });

  test("clicking New Project keeps an authenticated context", async ({ page, context }) => {
    const documentChain = recordDocumentChain(page);

    // Byte-for-byte the journey's preamble.
    await establishAuthenticatedSession(page);
    const afterProjects = await authSnapshot("after /projects", page, context);

    await page.getByRole("button", { name: /new project|create project/i }).first().click();
    const beforeInput = await authSnapshot("immediately after New Project click", page, context);
    const clickedAt = Date.now();

    // Race the two outcomes rather than waiting out a long timeout.
    const input = page.getByTestId("project-name-input");
    const signedOut = page.waitForURL(/\/sign-in/, { timeout: ENTRY_RACE_MS }).then(() => "sign-in");
    const interactable = input
      .waitFor({ state: "visible", timeout: ENTRY_RACE_MS })
      .then(() => "input");

    const outcome = await Promise.race([interactable, signedOut]).catch(() => "timeout");

    if (outcome !== "input") {
      const atRedirect = await authSnapshot("at first navigation after click", page, context);
      const firstHopAfterClick = documentChain.find((hop) => hop.at >= clickedAt) ?? null;

      const diagnostics = {
        outcome,
        clickedAt,
        firstDocumentHopAfterClick: firstHopAfterClick,
        msFromClickToFirstRedirect: firstHopAfterClick ? firstHopAfterClick.at - clickedAt : null,
        // A middleware redirect appears as a document response; a purely
        // client-side bounce leaves the chain untouched around the click.
        redirectWasServerSide: firstHopAfterClick !== null,
        documentChain,
        snapshots: [afterProjects, beforeInput, atRedirect],
      };

      expect(
        outcome,
        `Project entry lost the session. Structural diagnostics (no cookie values, no tokens):\n${JSON.stringify(
          diagnostics,
          null,
          2,
        )}`,
      ).toBe("input");
    }

    // Interactable, not merely present: the journey's fill() is what actually failed.
    await expect(input).toBeEditable({ timeout: 5_000 });
    expect(page.url(), "must remain on an authenticated route").not.toContain("/sign-in");
  });
});
