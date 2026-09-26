/**
 * PJ-01 step 4: observe processing exactly as a waiting user does, without reloading.
 *
 * Two independent signals on one clock:
 * - every documents-list response the APPLICATION requested on its own (the harness never
 *   triggers a request or reload), reduced to the uploaded document's backend stage;
 * - the status label the user can read on that document's row.
 *
 * `evaluateProcessingTimeline` then decides whether the UX was honest and self-updating.
 */
import type { Page, Response } from "@playwright/test";

import {
  evaluateProcessingTimeline,
  type PollObservation,
  type ProcessingEvaluation,
  type ProcessingTimeline,
  type UiObservation,
} from "../../../pj01/processing-evaluator";
import {
  classifyBackendDocument,
  classifyUiDocumentLabel,
  extractStatusLabel,
  isTerminalStage,
  type PolledDocument,
} from "../../../pj01/status-model";
import type { Pj01RunRecorder } from "./run-recorder";

export const ANALYSIS_BUDGET_MS = 240_000;

export interface ProcessingObservation {
  timeline: ProcessingTimeline;
  evaluation: ProcessingEvaluation;
  reloads: number;
}

export async function observeProcessingWithoutReload(
  page: Page,
  recorder: Pj01RunRecorder,
  options: { projectId: string; documentId: string; budgetMs?: number; sampleEveryMs?: number; labelGraceMs?: number },
): Promise<ProcessingObservation> {
  const { projectId, documentId } = options;
  const budgetMs = options.budgetMs ?? ANALYSIS_BUDGET_MS;
  const sampleEveryMs = options.sampleEveryMs ?? 2_000;
  const labelGraceMs = options.labelGraceMs ?? 12_000;

  const started = Date.now();
  const clock = (): number => Date.now() - started;
  const polls: PollObservation[] = [];
  const uiSamples: UiObservation[] = [];
  let reloads = 0;
  const documentsPath = new RegExp(`/projects/${projectId}/documents/?$`);
  const startUrl = page.url();

  const onResponse = async (response: Response): Promise<void> => {
    if (response.request().method() !== "GET" || !response.ok()) return;
    if (!documentsPath.test(new URL(response.url()).pathname)) return;
    const atMs = clock();
    try {
      const body = (await response.json()) as { items?: PolledDocument[] } | PolledDocument[];
      const items = Array.isArray(body) ? body : (body.items ?? []);
      const document = items.find((item) => item.id === documentId);
      if (document) polls.push({ atMs, stage: classifyBackendDocument(document) });
    } catch {
      // A body that cannot be read is not a backend stage; the gap check will surface it.
    }
  };
  const onNavigate = (): void => {
    if (page.url() === startUrl) reloads += 1;
  };
  page.on("response", onResponse);
  page.on("framenavigated", onNavigate);

  try {
    while (clock() < budgetMs) {
      const row = page.getByTestId(`document-row-${documentId}`);
      if ((await row.count()) > 0) {
        const label = extractStatusLabel(await row.innerText()) ?? "";
        uiSamples.push({ atMs: clock(), label });
      }

      const terminal = polls.find((poll) => isTerminalStage(poll.stage));
      if (terminal) {
        const latest = classifyUiDocumentLabel(uiSamples.at(-1)?.label ?? "");
        const settled =
          (terminal.stage === "analyzed" && latest === "success") || (terminal.stage === "error" && latest === "error");
        if (settled || clock() - terminal.atMs > labelGraceMs + sampleEveryMs) break;
      }
      await page.waitForTimeout(sampleEveryMs);
    }
  } finally {
    page.off("response", onResponse);
    page.off("framenavigated", onNavigate);
  }

  const timeline: ProcessingTimeline = {
    startedAtMs: 0,
    deadlineMs: budgetMs,
    polls,
    uiSamples,
    timedOut: !polls.some((poll) => isTerminalStage(poll.stage)),
  };
  const evaluation = evaluateProcessingTimeline(timeline, { labelGraceMs });

  recorder.record("processing", {
    outcome: evaluation.outcome,
    polls: polls.length,
    uiSamples: uiSamples.length,
    backendStages: [...new Set(polls.map((poll) => poll.stage))],
    uiLabels: [...new Set(uiSamples.map((sample) => sample.label))],
    msToTerminal: polls.find((poll) => isTerminalStage(poll.stage))?.atMs ?? null,
    reloads,
  });
  for (const violation of evaluation.violations) {
    recorder.violation(`PROCESSING_${violation.code}`, violation.detail);
  }
  if (reloads > 0) {
    recorder.violation("PROCESSING_PAGE_RELOADED", `the documents page reloaded ${reloads} time(s) during processing`);
  }
  return { timeline, evaluation, reloads };
}
