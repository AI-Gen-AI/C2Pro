/**
 * PJ-01 steps 5–6: reach Health through visible navigation and assert six dimensions.
 *
 * Health navigation (a "Health" project tab) is being delivered on its own branches, to
 * `/projects/{id}/health` or `/projects/{id}/analysis`; this harness accepts either and
 * records gap G4 when neither exists. The Health view must show the assessment without a
 * manual refresh once processing reported the document analyzed.
 */
import { expect, type Page, type Response } from "@playwright/test";

import {
  CANONICAL_CATEGORIES,
  evaluateHealthTileText,
  evaluateHealthVector,
  type HealthExpectations,
  type HealthVectorPayload,
} from "../../../pj01/health-evaluator";
import { findProjectTab, HEALTH_ROUTE_PATTERN, type NavLink, type ProjectTabKey } from "../../../pj01/navigation";
import type { Pj01RunRecorder } from "./run-recorder";

const PROJECT_TABS = 'nav[aria-label="Project tabs"] a';
const HEALTH_ERROR_STATES = ["health-loading", "health-error", "health-unavailable", "health-not-found"] as const;

export async function readProjectTabs(page: Page): Promise<NavLink[]> {
  await page.locator(PROJECT_TABS).first().waitFor({ state: "visible", timeout: 30_000 });
  return page
    .locator(PROJECT_TABS)
    .evaluateAll((links) =>
      links.map((link) => ({ name: (link.textContent ?? "").trim(), href: link.getAttribute("href") ?? "" })),
    );
}

/** Click a project tab if it exists; otherwise record `gapCode` and return false. */
export async function clickProjectTab(
  page: Page,
  recorder: Pj01RunRecorder,
  projectId: string,
  key: ProjectTabKey,
  gapCode: string,
): Promise<boolean> {
  const tabs = await readProjectTabs(page);
  const tab = findProjectTab(tabs, projectId, key);
  if (!tab) {
    recorder.gapOrStop(gapCode, `no visible "${key}" project tab (tabs: ${tabs.map((t) => t.name).join(", ")})`);
    return false;
  }
  await page.locator(`${PROJECT_TABS}[href="${tab.href}"]`).first().click();
  return true;
}

function isHealthResponse(response: Response, projectId: string): boolean {
  return (
    response.request().method() === "GET" &&
    response.ok() &&
    new RegExp(`/projects/${projectId}/health/?$`).test(new URL(response.url()).pathname)
  );
}

export async function openHealthThroughNavigation(
  page: Page,
  recorder: Pj01RunRecorder,
  options: { projectId: string; refetchWaitMs?: number },
): Promise<HealthVectorPayload> {
  const { projectId } = options;
  const refetchWaitMs = options.refetchWaitMs ?? 30_000;
  const vectors: HealthVectorPayload[] = [];
  const onResponse = async (response: Response): Promise<void> => {
    if (!isHealthResponse(response, projectId)) return;
    try {
      vectors.push((await response.json()) as HealthVectorPayload);
    } catch {
      // unreadable body: not a Health payload
    }
  };
  page.on("response", onResponse);

  try {
    const clicked = await clickProjectTab(page, recorder, projectId, "health", "G4_HEALTH_NOT_NAVIGABLE");
    if (clicked) {
      recorder.record("healthReachedBy", "project-tab");
    } else {
      // Diagnostic mode only (strict mode already stopped): continue to collect evidence.
      recorder.record("healthReachedBy", "typed-url (diagnostic mode)");
      await page.goto(`/projects/${projectId}/analysis`);
    }
    await page.waitForURL(HEALTH_ROUTE_PATTERN, { timeout: 30_000 });
    await expect(page.getByRole("region", { name: "Document health" })).toBeVisible({ timeout: 60_000 });
    await expect.poll(() => vectors.length, { timeout: 60_000 }).toBeGreaterThan(0);

    // The document is already analyzed: the assessment must arrive without a manual refresh.
    const deadline = Date.now() + refetchWaitMs;
    while (!vectors.at(-1)?.single_document_coverage && Date.now() < deadline) {
      await page.waitForTimeout(2_000);
    }
    if (!vectors.at(-1)?.single_document_coverage) {
      recorder.violation(
        "HEALTH_MANUAL_REFRESH_REQUIRED",
        `the document was analyzed but Health showed no assessment and did not refetch within ${refetchWaitMs}ms`,
      );
      if (recorder.mode === "strict") {
        throw new Error("PJ01_HEALTH_MANUAL_REFRESH_REQUIRED: Health did not update without a reload");
      }
      const reloadDeadline = Date.now() + 120_000;
      while (!vectors.at(-1)?.single_document_coverage && Date.now() < reloadDeadline) {
        await page.reload();
        await page.waitForTimeout(5_000);
      }
    }
    recorder.record("healthResponses", vectors.length);
    return vectors.at(-1) ?? {};
  } finally {
    page.off("response", onResponse);
  }
}

export async function assertSixHealthDimensions(
  page: Page,
  recorder: Pj01RunRecorder,
  vector: HealthVectorPayload,
  expectations: HealthExpectations,
): Promise<void> {
  const apiViolations = evaluateHealthVector(vector, expectations);
  for (const violation of apiViolations) recorder.violation(`HEALTH_${violation.code}`, violation.detail);

  await expect(page.getByTestId("health-granularity")).toBeVisible({ timeout: 30_000 });
  for (const state of HEALTH_ERROR_STATES) {
    await expect(page.getByTestId(state), `${state} must not remain on screen`).toHaveCount(0);
  }

  const tileViolations = [];
  for (const category of CANONICAL_CATEGORIES) {
    const tile = page.getByTestId(`health-category-${category}`);
    await expect(tile, `${category} tile must be visible`).toBeVisible();
    const assessment = vector.single_document_coverage?.assessments?.find((item) => item.category === category);
    for (const violation of evaluateHealthTileText(
      category,
      assessment?.state ?? "insufficient_evidence",
      await tile.innerText(),
    )) {
      tileViolations.push(violation);
      recorder.violation(`HEALTH_${violation.code}`, violation.detail);
    }
  }

  recorder.record(
    "healthStates",
    Object.fromEntries(
      (vector.single_document_coverage?.assessments ?? []).map((item) => [item.category, item.state]),
    ),
  );
  const all = [...apiViolations, ...tileViolations];
  if (all.length > 0) {
    throw new Error(`PJ01_HEALTH_SIX_DIMENSIONS: ${all.map((v) => `${v.code}(${v.category ?? "-"})`).join(", ")}`);
  }
}
