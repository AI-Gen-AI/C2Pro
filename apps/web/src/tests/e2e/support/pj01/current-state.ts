/**
 * PJ-01 step I: Current State around revision B, reached through the Report tab.
 *
 * Judges the application's own report response, the Health rows the user sees, and the JSON and
 * CSV files the user downloads, for six canonical categories, one logical document and reasons on
 * every unavailable section — in two phases:
 *
 * - `pending-review`: revision B is uploaded and analysed but NOT approved. The report must not
 *   present the document as analysed and must disclose the revision and the decision waiting;
 * - `approved`: the human approved revision B. Nothing may read as pending and Health must be
 *   computed at or after the approval (an earlier snapshot is the pre-approval state).
 */
import { readFileSync } from "node:fs";

import { expect, type Page, type Response } from "@playwright/test";

import {
  evaluateCurrentStateReport,
  evaluateExportParity,
  type CurrentStateReportLike,
  type ScreenHealthRow,
} from "../../../pj01/current-state-evaluator";
import {
  evaluateApprovedRevisionCurrentState,
  evaluatePendingRevisionCurrentState,
  parseInstant,
} from "../../../pj01/revision-authority-evaluator";
import { clickProjectTab } from "./health";
import type { Pj01RunRecorder } from "./run-recorder";

async function downloadText(page: Page, buttonName: RegExp): Promise<string> {
  const download = page.waitForEvent("download", { timeout: 30_000 });
  await page.getByRole("button", { name: buttonName }).click();
  const file = await (await download).path();
  if (!file) throw new Error(`PJ01_DOWNLOAD_FAILED: ${buttonName}`);
  return readFileSync(file, "utf8");
}

export type CurrentStatePhase = "pending-review" | "approved";

export async function assertCurrentStateThroughNavigation(
  page: Page,
  recorder: Pj01RunRecorder,
  options: { projectId: string; phase: CurrentStatePhase; approvedAt?: string; waitMs?: number },
): Promise<void> {
  const { projectId, phase } = options;
  const deadline = Date.now() + (options.waitMs ?? 60_000);
  const isReport = (response: Response): boolean =>
    response.request().method() === "GET" &&
    response.ok() &&
    new RegExp(`/projects/${projectId}/reports/current-state/?$`).test(new URL(response.url()).pathname);

  let report: CurrentStateReportLike;
  let attempts = 0;
  for (;;) {
    attempts += 1;
    if (attempts > 1) {
      // Come back to the report the way a person does: leave the tab and open it again.
      await clickProjectTab(page, recorder, projectId, "documents", "DOCUMENTS_TAB_NOT_NAVIGABLE");
      await page.waitForURL(new RegExp(`/projects/${projectId}/documents`), { timeout: 30_000 });
    }
    await clickProjectTab(page, recorder, projectId, "report", "REPORT_TAB_NOT_NAVIGABLE");
    await page.waitForURL(new RegExp(`/projects/${projectId}/report`), { timeout: 30_000 });
    // The report states what was known when it was generated and is only regenerated when the user
    // asks (by design): a copy opened earlier is reused on return. Ask for a current one.
    const regenerate = page.getByRole("button", { name: /^regenerate$/i });
    await expect(regenerate).toBeEnabled({ timeout: 120_000 });
    const reportResponse = page.waitForResponse(isReport, { timeout: 120_000 });
    await regenerate.click();
    report = (await (await reportResponse).json()) as CurrentStateReportLike;
    const asOf = report.sections.health?.source_as_of;
    const fresh = phase === "pending-review" || !options.approvedAt || (asOf != null && parseInstant(asOf) >= parseInstant(options.approvedAt));
    if (fresh || Date.now() > deadline) break;
    await page.waitForTimeout(3_000);
  }

  for (const violation of evaluateCurrentStateReport(report, {
    expectedDocumentTotal: 1,
    latestRevisionAnalyzedAt: phase === "approved" ? options.approvedAt : undefined,
  })) {
    recorder.violation(`CURRENT_STATE_${phase.toUpperCase()}_${violation.code}`, violation.detail);
  }
  const authority =
    phase === "pending-review"
      ? evaluatePendingRevisionCurrentState(report)
      : evaluateApprovedRevisionCurrentState(report, { approvedAt: options.approvedAt ?? "" });
  for (const violation of authority) {
    recorder.violation(`CURRENT_STATE_${phase.toUpperCase()}_${violation.code}`, violation.detail);
  }
  if (phase === "approved" && attempts > 1) {
    recorder.violation(
      "ANALYZED_BEFORE_CURRENT_STATE_REFRESH",
      `Current State still showed the pre-approval Health until the report was opened ${attempts} times`,
      { blocking: false },
    );
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
  await recorder.screenshot(page, `i-current-state-${phase}`);

  const json = await downloadText(page, /download json/i);
  const csv = await downloadText(page, /download csv/i);
  for (const violation of evaluateExportParity(report, json, csv, screen)) {
    recorder.violation(`CURRENT_STATE_${phase.toUpperCase()}_${violation.code}`, violation.detail);
  }

  recorder.record(`currentState.${phase}`, {
    schema: report.report_schema_version,
    attempts,
    healthStatus: report.sections.health?.status,
    healthSourceAsOf: report.sections.health?.source_as_of,
    categories: screen,
    documents: report.sections.documents?.data?.items?.map((item) => ({
      filename: item.filename,
      version: item.version,
      lifecycle: item.lifecycle_status,
    })),
    attention: report.sections.executive_summary?.data?.attention_items?.map((item) => item.kind),
    hitlSection: report.sections.hitl?.status,
    nonAvailableSections: Object.entries(report.sections)
      .filter(([, section]) => section && section.status !== "available")
      .map(([name, section]) => ({ name, status: section?.status, reason: section?.status_reason })),
  });
}
