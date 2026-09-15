/**
 * PJ-01 step H: What Changed? for the real revision B, reached through the project tab.
 *
 * Uses only the application's own timeline and change-detail responses. The revision identity
 * is read from the application, and its content hashes are checked against the committed
 * Contract A and B fixture files, so revision A's identity is proven unchanged by content.
 */
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";

import { expect, type Page, type Response } from "@playwright/test";

import type { Pj01ContractFixtureManifest } from "../../../pj01/fixture-contract";
import type { Pj01RevisionFixtureManifest } from "../../../pj01/revision-fixture";
import {
  evaluateChangeDetail,
  evaluateTimeline,
  type ChangeDetail,
  type RevisionChangeExpectation,
  type TimelineItem,
} from "../../../pj01/what-changed-evaluator";
import { clickProjectTab } from "./health";
import type { Pj01RunRecorder } from "./run-recorder";

const sha256 = (file: string): string => createHash("sha256").update(readFileSync(file)).digest("hex");

export interface WhatChangedResult {
  changeEventId: string;
  sourceRevisionId: string;
  targetRevisionId: string;
  occurredAt: string;
}

export async function assertWhatChangedThroughNavigation(
  page: Page,
  recorder: Pj01RunRecorder,
  options: {
    projectId: string;
    documentId: string;
    contractAPdf: string;
    contractBPdf: string;
    base: Pj01ContractFixtureManifest;
    revision: Pj01RevisionFixtureManifest;
    budgetMs?: number;
  },
): Promise<WhatChangedResult> {
  const { projectId, documentId } = options;
  const timelines: TimelineItem[][] = [];
  const onTimeline = async (response: Response): Promise<void> => {
    if (response.request().method() !== "GET" || !response.ok()) return;
    if (!new RegExp(`/projects/${projectId}/timeline/?$`).test(new URL(response.url()).pathname)) return;
    try {
      timelines.push(((await response.json()) as { items: TimelineItem[] }).items);
    } catch {
      // not a timeline body
    }
  };
  page.on("response", onTimeline);

  const expectation: RevisionChangeExpectation = {
    documentId,
    sourceRevisionId: "",
    targetRevisionId: "",
    sourceBlobHash: sha256(options.contractAPdf),
    targetBlobHash: sha256(options.contractBPdf),
    changeCause: options.revision.expected_revision_change.change_cause,
    changedFacts: options.revision.expected_revision_change.changed_facts,
    controlTexts: options.base.facts
      .filter((fact) => options.revision.expected_revision_change.no_change_control_fact_keys.includes(fact.key))
      .map((fact) => fact.text),
  };

  try {
    await clickProjectTab(page, recorder, projectId, "changes", "WHAT_CHANGED_TAB_NOT_NAVIGABLE");
    await page.waitForURL(new RegExp(`/projects/${projectId}/changes`), { timeout: 30_000 });

    // The page polls while a revision is being compared; wait for revision B's outcome without reloading.
    const budget = Date.now() + (options.budgetMs ?? 180_000);
    const latestChange = (): TimelineItem | undefined =>
      timelines.at(-1)?.find((item) => item.event_type === "revision.changed" && item.document_id === documentId);
    while (!latestChange() && Date.now() < budget) {
      await page.waitForTimeout(2_000);
    }
    const change = latestChange();
    if (!change) {
      recorder.violation("WHAT_CHANGED_NO_OUTCOME", "revision B's change never appeared on What Changed? without a reload");
      throw new Error("PJ01_WHAT_CHANGED_NO_OUTCOME");
    }
    expectation.sourceRevisionId = String(change.provenance.source_revision_id ?? "");
    expectation.targetRevisionId = String(change.provenance.target_revision_id ?? "");
    if (!expectation.sourceRevisionId || expectation.sourceRevisionId === expectation.targetRevisionId) {
      recorder.violation("REVISION_IDENTITY", "the change does not name two distinct revisions");
    }

    const items = timelines.at(-1) ?? [];
    for (const violation of evaluateTimeline(items, expectation)) recorder.violation(`WHAT_CHANGED_${violation.code}`, violation.detail);

    const card = page.getByTestId(`change-item-${change.event_id}`);
    await expect(card).toBeVisible({ timeout: 30_000 });
    await expect(card.getByText("Project evidence changed")).toBeVisible();
    await expect(card.getByText("Business state changed")).toBeVisible();
    await recorder.screenshot(page, "h1-what-changed");

    const detailResponse = page.waitForResponse(
      (response: Response) =>
        response.request().method() === "GET" &&
        new RegExp(`/projects/${projectId}/documents/${documentId}/changes/${expectation.targetRevisionId}/?$`).test(
          new URL(response.url()).pathname,
        ),
      { timeout: 60_000 },
    );
    await card.getByRole("link", { name: /view before, after & evidence/i }).click();
    const detail = (await (await detailResponse).json()) as ChangeDetail;
    for (const violation of evaluateChangeDetail(detail, expectation)) recorder.violation(`WHAT_CHANGED_${violation.code}`, violation.detail);

    const page2 = page.getByTestId("change-detail-page");
    await expect(page2).toBeVisible({ timeout: 30_000 });
    await expect(page2.getByRole("heading", { name: "Before" }).first()).toBeVisible();
    await expect(page2.getByRole("heading", { name: "After" }).first()).toBeVisible();
    for (const fact of expectation.changedFacts) {
      await expect(page2.getByText(fact.after_text, { exact: false }).first()).toBeVisible();
      await expect(page2.getByText(fact.before_text, { exact: false }).first()).toBeVisible();
    }
    await expect(page2.getByText("Source evidence unavailable")).toHaveCount(0);
    await recorder.screenshot(page, "h2-change-detail");

    const result = {
      changeEventId: change.event_id,
      sourceRevisionId: expectation.sourceRevisionId,
      targetRevisionId: expectation.targetRevisionId,
      occurredAt: change.occurred_at,
    };
    recorder.record("whatChanged", {
      ...result,
      changeCause: change.change_cause,
      timelineEventIds: items.map((item) => item.event_id),
      sourceBlobHashMatchesContractA: detail.provenance?.source_blob_hash === expectation.sourceBlobHash,
      targetBlobHashMatchesContractB: detail.provenance?.target_blob_hash === expectation.targetBlobHash,
    });
    return result;
  } finally {
    page.off("response", onTimeline);
  }
}
