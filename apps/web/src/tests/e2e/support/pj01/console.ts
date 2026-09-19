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

export function collectAttributableConsoleErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("console", (message: ConsoleMessage) => {
    if (message.type() !== "error") return;
    const text = message.text();
    if (IGNORED_CONSOLE_NOISE.some((pattern) => pattern.test(text))) return;
    errors.push(text);
  });
  return errors;
}
