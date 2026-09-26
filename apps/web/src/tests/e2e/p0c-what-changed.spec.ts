/** PJ-01: real-auth browser journey for the append-only P0c timeline. */

import { existsSync, readFileSync } from "node:fs";
import path from "node:path";

import { expect, test, type Page } from "@playwright/test";

import { establishAuthenticatedSession, observeAuth } from "./support/p0b-auth";

type FixtureEvent = { event_id: string; change_cause: string | null };
type Fixture = {
  project_id: string;
  document_id: string;
  revisions: Record<string, { revision_id: string; blob_hash: string }>;
  events: Record<string, FixtureEvent>;
};

const fixturePath = process.env.P0C_BROWSER_FIXTURE_PATH ?? path.join(process.cwd(), "playwright", ".p0c", "fixture.json");

function fixture(): Fixture {
  if (!existsSync(fixturePath)) {
    throw new Error(`P0C_BROWSER_FIXTURE_MISSING: run seed_p0c_browser_journey.py --output ${fixturePath}`);
  }
  return JSON.parse(readFileSync(fixturePath, "utf8")) as Fixture;
}

async function openTimeline(page: Page, data: Fixture) {
  const response = page.waitForResponse((candidate) =>
    candidate.url().includes(`/projects/${data.project_id}/timeline`) && candidate.status() === 200,
  );
  await page.goto(`/projects/${data.project_id}/changes`);
  await expect(page.getByTestId("project-changes-page")).toBeVisible();
  return (await response).json() as Promise<{ items: Array<{ event_id: string; change_cause: string | null }> }>;
}

test.describe("PJ-01: What Changed", () => {
  test.describe.configure({ mode: "serial", timeout: 120_000 });

  test("renders canonical B/C/D causes, ordering, evidence, and unavailable detail honestly", async ({ page, baseURL }) => {
    const data = fixture();
    const observation = observeAuth(page, baseURL ?? "http://localhost:3100");
    await establishAuthenticatedSession(page, observation);

    const timeline = await openTimeline(page, data);
    expect(timeline.items.map((item) => item.event_id)).toEqual([
      data.events.B.event_id,
      data.events.C.event_id,
      data.events.D.event_id,
    ]);
    expect(timeline.items.map((item) => item.change_cause)).toEqual([
      "BUSINESS_STATE_CHANGED", "NEWLY_DISCOVERED", null,
    ]);
    await expect(page.getByText("Business state changed")).toBeVisible();
    await expect(page.getByText("Newly discovered")).toBeVisible();
    await expect(page.getByText("No change")).toBeVisible();

    // C retains B's evidence but records a distinct semantic conclusion.
    await page.goto(`/projects/${data.project_id}/changes/${data.document_id}/${data.revisions.B.revision_id}`);
    await expect(page.getByTestId("change-detail-page")).toBeVisible();
    await expect(page.getByText("NEWLY_DISCOVERED")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Before" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "After" })).toBeVisible();
    await expect(page.getByText("Completion is due on 30 June 2026.")).toBeVisible();
    await expect(page.getByText("Completion is due on 31 July 2026.")).toBeVisible();
    await expect(page.getByText("PJ-01 Contract: Clause 4.2")).toBeVisible();

    await page.goto(`/projects/${data.project_id}/changes/${data.document_id}/${data.revisions.D.revision_id}`);
    await expect(page.getByTestId("change-detail-page")).toBeVisible();
    await expect(page.getByText("No material change")).toBeVisible();
    await expect(page.getByText("The comparison completed with no material differences.")).toBeVisible();

    await page.goto(`/projects/${data.project_id}/changes/${data.document_id}/00000000-0000-0000-0000-000000000000`);
    await expect(page.getByText("This change detail is unavailable.")).toBeVisible();
  });
});
