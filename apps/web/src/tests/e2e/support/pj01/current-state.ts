/**
 * PJ-01 step I: Current State after revision B, reached through the Report tab.
 *
 * Judges the application's own report response, the Health rows the user sees, and the JSON and
 * CSV files the user downloads, for six canonical categories, one logical document, reasons on
 * every unavailable section, and Health that is not older than revision B's analysis.
 */
import { readFileSync } from "node:fs";

import { expect, type Page, type Response } from "@playwright/test";

import {
  evaluateCurrentStateReport,
  evaluateExportParity,
  type CurrentStateReportLike,
  type ScreenHealthRow,
} from "../../../pj01/current-state-evaluator";
import { clickProjectTab } from "./health";
import type { Pj01RunRecorder } from "./run-recorder";

async function downloadText(page: Page, buttonName: RegExp): Promise<string> {
  const download = page.waitForEvent("download", { timeout: 30_000 });
  await page.getByRole("button", { name: buttonName }).click();
  const file = await (await download).path();
  if (!file) throw new Error(`PJ01_DOWNLOAD_FAILED: ${buttonName}`);
  return readFileSync(file, "utf8");
}

export async function assertCurrentStateThroughNavigation(
  page: Page,
  recorder: Pj01RunRecorder,
  options: { projectId: string; latestRevisionAnalyzedAt: string },
): Promise<void> {
  const { projectId } = options;
  const reportResponse = page.waitForResponse(
    (response: Response) =>
      response.request().method() === "GET" &&
      response.ok() &&
      new RegExp(`/projects/${projectId}/reports/current-state/?$`).test(new URL(response.url()).pathname),
    { timeout: 120_000 },
  );
  await clickProjectTab(page, recorder, projectId, "report", "REPORT_TAB_NOT_NAVIGABLE");
  await page.waitForURL(new RegExp(`/projects/${projectId}/report`), { timeout: 30_000 });
  const report = (await (await reportResponse).json()) as CurrentStateReportLike;

  for (const violation of evaluateCurrentStateReport(report, {
    expectedDocumentTotal: 1,
    latestRevisionAnalyzedAt: options.latestRevisionAnalyzedAt,
  })) {
    recorder.violation(`CURRENT_STATE_${violation.code}`, violation.detail);
  }

  const healthCard = page.getByTestId("section-health");
  await expect(healthCard).toBeVisible({ timeout: 60_000 });
  const screen: ScreenHealthRow[] = await healthCard.getByTestId("health-category").evaluateAll((rows) =>
    rows.map((row) => ({
      category: row.getAttribute("data-category") ?? "",
      state: row.getAttribute("data-state") ?? "",
      evidenceCount: row.getAttribute("data-evidence-count") ?? "",
    })),
  );
  await recorder.screenshot(page, "i1-current-state");

  const json = await downloadText(page, /download json/i);
  const csv = await downloadText(page, /download csv/i);
  for (const violation of evaluateExportParity(report, json, csv, screen)) {
    recorder.violation(`CURRENT_STATE_${violation.code}`, violation.detail);
  }

  recorder.record("currentState", {
    schema: report.report_schema_version,
    healthStatus: report.sections.health?.status,
    healthSourceAsOf: report.sections.health?.source_as_of,
    categories: screen,
    documentsTotal: report.sections.documents?.data?.total,
    nonAvailableSections: Object.entries(report.sections)
      .filter(([, section]) => section && section.status !== "available")
      .map(([name, section]) => ({ name, status: section?.status, reason: section?.status_reason })),
  });
}
