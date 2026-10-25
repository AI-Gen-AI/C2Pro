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
  type BackendDocumentStage,
  classifyUiDocumentLabel,
  extractStatusLabel,
  isSettledStage,
  type PolledDocument,
  type Settlement,
} from "../../../pj01/status-model";
import type { Pj01RunRecorder } from "./run-recorder";

export const ANALYSIS_BUDGET_MS = 240_000;

export interface DocumentsAnswerTracker {
  /** The backend stage of the document in the application's most recent documents answer. */
  latest(): BackendDocumentStage | null;
  /** Forget what was answered so far (a new revision starts a new history). */
  reset(): void;
  stop(): void;
}

/**
 * Remember what the APPLICATION's own documents requests answered, without making any request.
 *
 * A wait that starts after the page already settled (the pipeline can finish between the upload
 * answer and the first poll) would otherwise see no answer at all and read as "never refreshed".
 * The last answer received since the upload was accepted is the honest starting point of the wait.
 */
export function trackDocumentsAnswers(page: Page, projectId: string, documentId: string): DocumentsAnswerTracker {
  const documentsPath = new RegExp(`/projects/${projectId}/documents/?$`);
  let latest: BackendDocumentStage | null = null;
  const onResponse = async (response: Response): Promise<void> => {
    if (response.request().method() !== "GET" || !response.ok()) return;
    if (!documentsPath.test(new URL(response.url()).pathname)) return;
    try {
      const body = (await response.json()) as { items?: PolledDocument[] } | PolledDocument[];
      const document = (Array.isArray(body) ? body : (body.items ?? [])).find((item) => item.id === documentId);
      if (document) latest = classifyBackendDocument(document);
    } catch {
      // unreadable body: keep the previous answer
    }
  };
  page.on("response", onResponse);
  return {
    latest: () => latest,
    reset: () => {
      latest = null;
    },
    stop: () => {
      page.off("response", onResponse);
    },
  };
}

export interface ProcessingObservation {
  timeline: ProcessingTimeline;
  evaluation: ProcessingEvaluation;
  reloads: number;
}

export async function observeProcessingWithoutReload(
  page: Page,
  recorder: Pj01RunRecorder,
  options: {
    projectId: string;
    documentId: string;
    budgetMs?: number;
    sampleEveryMs?: number;
    labelGraceMs?: number;
    /** Where this wait ends: the analysis finished (default) or it reached a human-review gate. */
    settlement?: Settlement;
    /**
     * The user action that STARTS the observed period (e.g. leaving the review page for the
     * Documents tab). It runs after the listeners are attached, so the very first documents answer
     * it provokes is observed: a state that is already settled when the page loads must not look
     * like "no refresh ever happened".
     */
    trigger?: () => Promise<void>;
    /** The last documents answer seen before this wait began (see {@link trackDocumentsAnswers}). */
    seedStage?: BackendDocumentStage | null;
  },
): Promise<ProcessingObservation> {
  const { projectId, documentId } = options;
  const budgetMs = options.budgetMs ?? ANALYSIS_BUDGET_MS;
  const sampleEveryMs = options.sampleEveryMs ?? 2_000;
  const labelGraceMs = options.labelGraceMs ?? 12_000;
  const settlement = options.settlement ?? "analyzed";

  const started = Date.now();
  const clock = (): number => Date.now() - started;
  const polls: PollObservation[] = [];
  const uiSamples: UiObservation[] = [];
  let reloads = 0;
  const reloadLog: { atMs: number; url: string }[] = [];
  const documentsPath = new RegExp(`/projects/${projectId}/documents/?$`);
  let startUrl = page.url();

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
    if (page.url() === startUrl) {
      reloads += 1;
      reloadLog.push({ atMs: clock(), url: page.url() });
    }
  };
  page.on("response", onResponse);
  page.on("framenavigated", onNavigate);

  if (options.seedStage) polls.push({ atMs: 0, stage: options.seedStage });

  try {
    if (options.trigger) {
      await options.trigger();
      startUrl = page.url();
    }
    while (clock() < budgetMs) {
      const row = page.getByTestId(`document-row-${documentId}`);
      if ((await row.count()) > 0) {
        const label = extractStatusLabel(await row.innerText()) ?? "";
        uiSamples.push({ atMs: clock(), label });
      }

      const terminal = polls.find((poll) => isSettledStage(poll.stage, settlement));
      if (terminal) {
        const latest = classifyUiDocumentLabel(uiSamples.at(-1)?.label ?? "");
        const settled =
          (terminal.stage === "analyzed" && latest === "success") ||
          (terminal.stage === "error" && latest === "error") ||
          (terminal.stage === "review_required" && latest === "needs_review");
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
    timedOut: !polls.some((poll) => isSettledStage(poll.stage, settlement)),
  };
  const evaluation = evaluateProcessingTimeline(timeline, { labelGraceMs, settlement });

  recorder.record("processing", {
    outcome: evaluation.outcome,
    polls: polls.length,
    uiSamples: uiSamples.length,
    backendStages: [...new Set(polls.map((poll) => poll.stage))],
    uiLabels: [...new Set(uiSamples.map((sample) => sample.label))],
    settlement,
    msToTerminal: polls.find((poll) => isSettledStage(poll.stage, settlement))?.atMs ?? null,
    reloads,
    reloadLog,
    seededStage: options.seedStage ?? null,
  });
  for (const violation of evaluation.violations) {
    recorder.violation(`PROCESSING_${violation.code}`, violation.detail);
  }
  if (reloads > 0) {
    recorder.violation("PROCESSING_PAGE_RELOADED", `the documents page reloaded ${reloads} time(s) during processing (at ${reloadLog.map((entry) => `${entry.atMs}ms`).join(", ")})`);
  }
  return { timeline, evaluation, reloads };
}
