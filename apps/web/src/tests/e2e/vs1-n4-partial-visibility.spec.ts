/**
 * FG-1a — genuine browser + Clerk DEVELOPMENT JWT + FastAPI + disposable PG.
 * Four synthetic candidates are preseeded into migrated PG. No model providers,
 * no MSW, no approval writes, no PDF correctness assertion.
 */
import { readFileSync } from "node:fs";
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { signInAsJourneyUser } from "./support/pj01/session";

type Fixture = {
  projectId: string;
  documentId: string;
  tenantId: string;
  runId: string;
  revisionId: string;
  foreignProjectId: string;
  fixtureMode: "SYNTHETIC_N4_NO_MODEL";
  findingsCount: 4;
  preexistingReceipts: 1;
};
const fixture = JSON.parse(
  readFileSync(path.join(process.cwd(), "playwright-report", "vs1-browser-fixture.json"), "utf8"),
) as Fixture;

async function scopedRequest(page: Page, url: string, method: "GET" | "POST" = "GET") {
  // Browser holds genuine Clerk Development identity. Do not export JWT or cookies
  // to Node, test logs or artifacts.
  return page.evaluate(async ({url, method}) => {
    const token = await window.Clerk?.session?.getToken();
    if (!token) throw new Error("VS1_CLERK_TOKEN_MISSING");
    const response = await fetch(url, {
      method,
      headers: { Authorization: `Bearer ${token}` },
    });
    const data = await response.json().catch(() => null);
    return {status: response.status, data};
  }, {url, method});
}

test.describe("FG-1a partial N4 (real browser, real Dev Clerk, real PG)", () => {
  test("shows proposed evidence and survives fresh session without unsafe retry", async ({browser, baseURL}) => {
    test.setTimeout(280_000);
    expect(process.env.ENVIRONMENT).toBe("test");
    expect(process.env.C2PRO_AI_MOCK).toBe("1");
    expect(fixture.fixtureMode).toBe("SYNTHETIC_N4_NO_MODEL");
    const base = baseURL ?? "http://localhost:3100";
    const firstContext = await browser.newContext({
      baseURL: base, storageState: {cookies: [], origins: []},
    });
    let secondContext: typeof firstContext | undefined;
    try {
      const page = await firstContext.newPage();
      await signInAsJourneyUser(page, base);
      await page.goto(`/projects/${fixture.projectId}/documents`);
      await expect(page.getByTestId("documents-page")).toBeVisible({timeout: 45000});

      const doc = page.getByTestId(`document-row-${fixture.documentId}`);
      await expect(doc).toBeVisible();
      await expect(doc).toContainText("Partial N4 results");
      await expect(doc.getByRole("link", {name: "View N4 findings"})).toBeVisible();
      await expect(doc.getByRole("button", {name: /Retry processing/i})).toHaveCount(0);

      await doc.getByRole("link", {name: "View N4 findings"}).click();
      await expect(page.getByTestId("n4-coverage")).toContainText(
        "2/2 windows with persisted results", {timeout: 45000},
      );
      await expect(page.getByTestId("n4-coverage")).toContainText("1 examined");
      await expect(page.getByTestId("n4-coverage")).toContainText("1 blocked");
      await expect(page.getByTestId("n4-unresolved")).toContainText("Annex C");
      await expect(page.getByTestId("n4-proposed-finding")).toHaveCount(4);
      await expect(page.getByText("FAT milestone exposure")).toBeVisible();
      await expect(page.getByText("The FAT shall be inspected")).toBeVisible();
      await expect(page.getByText("Citation not located in the N2 text.")).toBeVisible();
      await expect(page.getByText("original PDF not verified.", {exact: false}).first()).toBeVisible();
      await expect(page.getByRole("button", {name:/Approve|Reject|Retry|Confirm/i})).toHaveCount(0);

      // API queries are genuine authenticated GET/POST through the web proxy.
      const url = `/api/v1/projects/${fixture.projectId}/documents/${fixture.documentId}/n4-findings`;
      const get = await scopedRequest(page, url);
      expect(get.status).toBe(200);
      expect((get.data as {approvable?: boolean})?.approvable).toBe(false);

      const unsafePost = await scopedRequest(
        page, `/api/v1/projects/${fixture.projectId}/documents/${fixture.documentId}/reprocess`, "POST",
      );
      expect(unsafePost.status, "server guards unsafe reprocessing, not just the UI").toBe(409);

      const crossProject = await scopedRequest(
        page, `/api/v1/projects/${fixture.foreignProjectId}/documents/${fixture.documentId}/n4-findings`,
      );
      expect(crossProject.status, "foreign project does not reveal source candidates").toBe(404);

      await page.reload({waitUntil: "domcontentloaded"});
      await expect(page.getByTestId("n4-proposed-finding")).toHaveCount(4, {timeout:45000});
      await firstContext.close();

      // Deliberately NEW browser context with NO saved session or auth state.
      secondContext = await browser.newContext({
        baseURL: base, storageState: {cookies: [], origins: []},
      });
      const again = await secondContext.newPage();
      await signInAsJourneyUser(again, base);
      await again.goto(`/projects/${fixture.projectId}/documents/${fixture.documentId}/n4-findings`);
      await expect(again.getByTestId("n4-coverage")).toContainText(
        "2/2 windows with persisted results", {timeout: 45000},
      );
      await expect(again.getByTestId("n4-proposed-finding")).toHaveCount(4);
      await expect(again.getByRole("button", {name:/Approve|Reject|Retry/i})).toHaveCount(0);
    } finally {
      await secondContext?.close();
      await firstContext.close().catch(() => {});
    }
  });
});
