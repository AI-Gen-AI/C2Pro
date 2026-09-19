import { expect, test } from "@playwright/test";

import { createProjectThroughUi, signInAsJourneyUser } from "./support/pj01/session";

test.describe("TS-E2E-PJ01-CREATE-001: browser-visible project creation", () => {
  test.skip(
    process.env.PJ01_FOCAL_CREATE_PROJECT !== "1",
    "focal create-project qualification runs only when explicitly requested",
  );
  test.describe.configure({ timeout: 150_000 });

  test("accepts the browser-visible create-project response", async ({ baseURL, page }) => {
    const observation = await signInAsJourneyUser(page, baseURL ?? "http://localhost:3100");
    const projectId = await createProjectThroughUi(page, observation, `PJ-01 observer ${new Date().toISOString()}`);
    expect(projectId).toMatch(/^[0-9a-f-]{36}$/);
  });
});
