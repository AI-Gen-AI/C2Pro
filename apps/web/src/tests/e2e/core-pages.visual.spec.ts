/**
 * Backlog Task: TASK-021
 * Scope: Visual regression across core frontend pages
 */
import { expect, test } from "@playwright/test";

const corePages = [
  {
    name: "demo-documents",
    path: "/demo/documents",
    readyHeading: /documents/i,
  },
  {
    name: "demo-alerts",
    path: "/demo/alerts",
    readyHeading: /alerts/i,
  },
  {
    name: "demo-stakeholders",
    path: "/demo/stakeholders",
    readyHeading: /stakeholders/i,
  },
  {
    name: "demo-raci",
    path: "/demo/raci",
    readyHeading: /raci matrix/i,
  },
  {
    name: "demo-evidence-entry",
    path: "/demo/evidence",
    readyHeading: /evidence review/i,
  },
] as const;

test.describe("TASK-021 visual regression coverage for core pages", () => {
  test.describe.configure({ mode: "serial" });
  test.setTimeout(90_000);

  for (const corePage of corePages) {
    test(`${corePage.name} matches the approved desktop baseline`, async ({
      page,
    }) => {
      await page.emulateMedia({ reducedMotion: "reduce" });
      await page.goto(corePage.path, { waitUntil: "domcontentloaded" });

      await expect(
        page.getByRole("heading", { name: corePage.readyHeading }).first(),
      ).toBeVisible();
      await page.waitForLoadState("networkidle");

      await expect(page).toHaveScreenshot(`${corePage.name}.png`, {
        fullPage: true,
        animations: "disabled",
        caret: "hide",
        scale: "css",
        maxDiffPixelRatio: 0.01,
      });
    });
  }
});
