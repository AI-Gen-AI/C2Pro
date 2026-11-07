/**
 * UX-E2E-01 — real Clerk Development A/B browser gate on disposable DB.
 * No provider calls and no HITL actions. Creates only one synthetic project.
 */
import { expect, test } from "@playwright/test";

import { callApi } from "./support/integral/api";
import { clerkIdentity, DENIAL, denialsFor, developmentBEmail, signInTenantB } from "./support/integral/identity";
import { createProjectThroughUi, signInAsJourneyUser } from "./support/pj01/session";

const EMPTY_SESSION = { cookies: [], origins: [] };

test("UX-E2E-01: four-source onboarding, mobile and tenant A/B isolation", async ({ browser, baseURL }) => {
  test.setTimeout(240_000);
  const base = baseURL ?? "http://localhost:3100";
  const bEmail = developmentBEmail();
  expect(bEmail, "Clerk Development tenant B must be configured; no substitute is allowed").not.toBe("");

  const contextA = await browser.newContext({ baseURL: base, storageState: EMPTY_SESSION });
  const pageA = await contextA.newPage();
  try {
    const observer = await signInAsJourneyUser(pageA, base);
    const userA = await clerkIdentity(pageA);
    expect(userA.userId).not.toBe("");
    expect(userA.tenantId).not.toBe("");
    const projectId = await createProjectThroughUi(pageA, observer, "UX QA synthetic " + Date.now());

    const own = await callApi(pageA, "/api/v1/projects/" + projectId);
    expect(own.status, "A is authorized to read own project").toBe(200);
    await expect(pageA.getByTestId("epc-four-source-workflow")).toBeVisible();
    await expect(pageA.getByTestId("epc-source-category-count")).toContainText("0 of 4 types registered");
    await expect(pageA.getByTestId("technical-specification-slot")).toBeVisible();
    await expect(pageA.getByText("Required document triplet")).toBeVisible();

    await pageA.setViewportSize({ width: 390, height: 844 });
    await pageA.goto("/projects/" + projectId + "/documents");
    await expect(pageA.getByTestId("documents-page")).toBeVisible();
    await expect(pageA.getByTestId("technical-specification-slot")).toBeVisible();
    await pageA.goto("/projects/" + projectId + "/review");
    await expect(pageA.getByTestId("review-page")).toBeVisible();
    await expect(pageA.getByTestId("stat-pending")).toBeVisible();

    const tenantB = await signInTenantB(browser, base, bEmail);
    try {
      const userB = await clerkIdentity(tenantB.page);
      expect(userB.userId).not.toBe(userA.userId);
      expect(userB.tenantId).not.toBe(userA.tenantId);
      const statuses = await denialsFor(tenantB.page, projectId);
      expect(statuses).toHaveLength(4);
      for (const status of statuses) {
        expect(DENIAL, "tenant B must not read tenant A project, documents, alerts or health").toContain(status);
      }
    } finally {
      await tenantB.close();
    }
  } finally {
    await contextA.close();
  }
});
