/**
 * Self-test of the integral runner's findings-panel wait (run 41404854469 returned ZERO decisions for a candidate that
 * had five findings: the panel first painted a cached empty read and the runner counted at that first paint).
 * It needs no Clerk, no backend and no web server: the panel is a static page whose list is filled late -- or never.
 * It exercises the runner's own `awaitFindingsPanel` with real Playwright locators.
 */
import { expect, test, type Page } from "@playwright/test";

import { awaitFindingsPanel } from "./support/integral/flow";

const ROW = "11111111-1111-4111-8111-111111111111";

/** A card whose findings panel lists `initial` findings now and `later` findings after `afterMs` (never when null). */
async function mountPanel(page: Page, options: { row?: string; initial: number; later?: number; afterMs?: number }) {
  await page.setContent(`
    <div id="card">
      <section aria-label="Findings of this analysis" data-testid="review-findings-${options.row ?? ROW}">
        <p>${options.initial} findings in this analysis</p>
        <p data-testid="review-findings-scope-${options.row ?? ROW}">Decisions here are provisional notes by you.</p>
        <ul id="list">${Array.from({ length: options.initial }, (_, i) => `<li data-testid="finding-${i}">f${i}</li>`).join("")}</ul>
      </section>
    </div>
    <script>
      const later = ${options.later ?? "null"};
      if (later !== null) setTimeout(() => {
        document.getElementById("list").innerHTML = Array.from({ length: later }, (_, i) => '<li data-testid="finding-' + i + '">f' + i + '</li>').join("");
      }, ${options.afterMs ?? 0});
    </script>`);
  return page.locator("#card");
}

test.describe("integral runner: findings panel wait", () => {
  test("waits out a first paint with zero findings and resolves once the fresh read shows the five seeded ones", async ({ page }) => {
    const card = await mountPanel(page, { initial: 0, later: 5, afterMs: 800 });
    const reading = await awaitFindingsPanel(card, { findings: 5, reviewRowId: ROW });
    expect(reading).toEqual({ reviewRowId: ROW, findings: 5 });
  });

  test("RED reproduction: counting at the first paint (the pre-fix runner) reads ZERO on the very same page", async ({ page }) => {
    const card = await mountPanel(page, { initial: 0, later: 5, afterMs: 800 });
    const region = card.getByRole("region", { name: "Findings of this analysis" });
    await region.waitFor({ state: "visible" });
    const atFirstPaint = await region.locator("li[data-testid^='finding-']").count();
    expect(atFirstPaint, "the old runner took its decisions from this number").toBe(0);
    await expect(region.locator("li[data-testid^='finding-']")).toHaveCount(5); // the fresh read does arrive
  });

  test("a PERSISTENT discrepancy is an explicit failure naming both numbers, never a success with zero", async ({ page }) => {
    const card = await mountPanel(page, { initial: 0 });
    await expect(awaitFindingsPanel(card, { findings: 5, reviewRowId: ROW }, 1_500)).rejects.toThrow(
      /INTEGRAL_FINDINGS_PANEL_COUNT_MISMATCH: the panel shows 0 finding\(s\) but the seed created 5/,
    );
  });

  test("a panel bound to another review row fails at once, without waiting for the count", async ({ page }) => {
    const card = await mountPanel(page, { row: "22222222-2222-4222-8222-222222222222", initial: 5 });
    const started = Date.now();
    await expect(awaitFindingsPanel(card, { findings: 5, reviewRowId: ROW })).rejects.toThrow(/INTEGRAL_FINDINGS_PANEL_ROW_MISMATCH/);
    expect(Date.now() - started).toBeLessThan(5_000);
  });

  test("more findings than seeded is also a mismatch", async ({ page }) => {
    const card = await mountPanel(page, { initial: 6 });
    await expect(awaitFindingsPanel(card, { findings: 5, reviewRowId: ROW }, 1_000)).rejects.toThrow(/shows 6 finding\(s\) but the seed created 5/);
  });

  test("a card with no findings panel at all is an explicit failure", async ({ page }) => {
    await page.setContent('<div id="card"><p>nothing here</p></div>');
    await expect(awaitFindingsPanel(page.locator("#card"), { findings: 5, reviewRowId: ROW }, 1_000)).rejects.toThrow(/INTEGRAL_FINDINGS_PANEL_NOT_SURFACED/);
  });

  test("the wait never exceeds the 30 s ceiling even if asked for more", async () => {
    // Pure contract check: the ceiling is a constant of the helper, not a fixed sleep.
    const { FINDINGS_PANEL_BUDGET_MS } = await import("./support/integral/flow");
    expect(FINDINGS_PANEL_BUDGET_MS).toBe(30_000);
  });
});
