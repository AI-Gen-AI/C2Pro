/**
 * Attributable browser console errors for PJ-01.
 *
 * The ignore list is deliberately narrow and named (same rationale as the P0b journey):
 * anything attributable to the journey surfaces, including CORS and network failures,
 * must still fail the run.
 */
import type { ConsoleMessage, Page } from "@playwright/test";

export const IGNORED_CONSOLE_NOISE: readonly RegExp[] = [
  // Clerk/telemetry/analytics chatter is not a PJ-01 regression signal.
  /clerk|telemetry|favicon|analytics|third-party/i,
  // Emitted by Next's dev renderer on every page; not produced by journey components.
  /Encountered a script tag while rendering React component/i,
];

/**
 * Messages emitted by a third party's own frame or script (Clerk, its bot-challenge provider) are not the
 * application's: the sign-out step visits the hosted /sign-in surface, where such a frame reports a CSP note
 * (a continuation line that carries none of the words above). Decided by WHERE the message comes from, not by
 * its text, so an error raised by C2Pro's own code or origin is never excluded.
 */
export const THIRD_PARTY_ORIGIN = /(^|\.)(clerk\.[a-z.]+|clerk\.com|clerk\.accounts\.dev|cloudflare\.com)(\/|:|$)/i;

function originOf(url: string): string {
  try {
    return new URL(url).host;
  } catch {
    return "";
  }
}

export function collectAttributableConsoleErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("console", (message: ConsoleMessage) => {
    if (message.type() !== "error") return;
    const text = message.text();
    if (IGNORED_CONSOLE_NOISE.some((pattern) => pattern.test(text))) return;
    const source = message.location().url ?? "";
    if (THIRD_PARTY_ORIGIN.test(originOf(source))) return;
    // Say where it came from, so a red run explains itself.
    errors.push(source ? `${text} [from ${source.split("?")[0]}]` : text);
  });
  return errors;
}
