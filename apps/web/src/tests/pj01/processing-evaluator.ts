/**
 * PJ-01 processing UX evaluator.
 *
 * Judges a timeline recorded in the browser WITHOUT page reloads:
 * - `polls`: document-list responses the application requested on its own, reduced to the
 *   backend stage of the uploaded document;
 * - `uiSamples`: the status label the user could read on that document's row.
 *
 * It prevents the failure modes a green backend hides: an indefinite spinner, a UI that
 * needs a manual refresh, success shown before analysis finished, and a backend error
 * disguised as progress.
 */
import {
  classifyUiDocumentLabel,
  isTerminalStage,
  type BackendDocumentStage,
  type UiDocumentState,
} from "./status-model";

export interface PollObservation {
  atMs: number;
  stage: BackendDocumentStage;
}

export interface UiObservation {
  atMs: number;
  label: string;
}

export interface ProcessingTimeline {
  /** When the upload was accepted (all times share one clock). */
  startedAtMs: number;
  /** The processing budget, as an absolute time on the same clock. */
  deadlineMs: number;
  polls: PollObservation[];
  uiSamples: UiObservation[];
  /** True when observation stopped because the budget ran out. */
  timedOut?: boolean;
}

export interface ProcessingOptions {
  /** Longest acceptable gap between app-initiated polls while the document is in flight. */
  maxPollGapMs?: number;
  /** How long a label may lag behind a backend transition before it counts as stale. */
  labelGraceMs?: number;
}

export type ProcessingViolationCode =
  | "FALSE_SUCCESS"
  | "HIDDEN_ERROR"
  | "MANUAL_REFRESH_REQUIRED"
  | "NO_AUTO_REFRESH"
  | "INDEFINITE_SPINNER"
  | "DOCUMENT_NOT_VISIBLE";

export interface ProcessingViolation {
  code: ProcessingViolationCode;
  atMs: number;
  detail: string;
}

export interface ProcessingEvaluation {
  outcome: "analyzed" | "error" | "timeout" | "incomplete";
  violations: ProcessingViolation[];
}

export const DEFAULT_MAX_POLL_GAP_MS = 15_000;
export const DEFAULT_LABEL_GRACE_MS = 12_000;

export function evaluateProcessingTimeline(
  timeline: ProcessingTimeline,
  options: ProcessingOptions = {},
): ProcessingEvaluation {
  const maxPollGapMs = options.maxPollGapMs ?? DEFAULT_MAX_POLL_GAP_MS;
  const labelGraceMs = options.labelGraceMs ?? DEFAULT_LABEL_GRACE_MS;
  const polls = [...timeline.polls].sort((a, b) => a.atMs - b.atMs);
  const uiSamples = [...timeline.uiSamples].sort((a, b) => a.atMs - b.atMs);

  const violations: ProcessingViolation[] = [];
  const report = (code: ProcessingViolationCode, atMs: number, detail: string): void => {
    if (!violations.some((violation) => violation.code === code)) violations.push({ code, atMs, detail });
  };

  const terminal = polls.find((poll) => isTerminalStage(poll.stage));
  const outcome: ProcessingEvaluation["outcome"] = terminal
    ? (terminal.stage as "analyzed" | "error")
    : timeline.timedOut
      ? "timeout"
      : "incomplete";

  const stageAt = (atMs: number): BackendDocumentStage | null => {
    let stage: BackendDocumentStage | null = null;
    for (const poll of polls) {
      if (poll.atMs > atMs) break;
      stage = poll.stage;
    }
    return stage;
  };

  if (uiSamples.length === 0) {
    report(
      "DOCUMENT_NOT_VISIBLE",
      polls.at(-1)?.atMs ?? timeline.startedAtMs,
      "the uploaded document never appeared as a row the user could read",
    );
  }

  for (const sample of uiSamples) {
    const uiState: UiDocumentState = classifyUiDocumentLabel(sample.label);
    const stage = stageAt(sample.atMs);

    if (uiState === "success" && stage !== null && stage !== "analyzed") {
      report("FALSE_SUCCESS", sample.atMs, `UI showed "${sample.label}" while the backend stage was ${stage}`);
    }
    if (terminal && sample.atMs - terminal.atMs > labelGraceMs) {
      if (terminal.stage === "analyzed" && uiState !== "success") {
        report(
          "MANUAL_REFRESH_REQUIRED",
          sample.atMs,
          `analysis completed at ${terminal.atMs}ms but the UI still showed "${sample.label}"`,
        );
      }
      if (terminal.stage === "error" && uiState !== "error") {
        report(
          "HIDDEN_ERROR",
          sample.atMs,
          `the backend failed at ${terminal.atMs}ms but the UI still showed "${sample.label}"`,
        );
      }
    }
  }

  // Auto-refresh: while the document is in flight the application itself must keep polling.
  const inFlightEnd = terminal?.atMs ?? (timeline.timedOut ? timeline.deadlineMs : polls.at(-1)?.atMs);
  if (inFlightEnd !== undefined) {
    const checkpoints = [
      timeline.startedAtMs,
      ...polls.filter((poll) => poll.atMs <= inFlightEnd).map((poll) => poll.atMs),
    ];
    if (!terminal && timeline.timedOut) checkpoints.push(timeline.deadlineMs);
    for (let index = 1; index < checkpoints.length; index += 1) {
      const gap = checkpoints[index] - checkpoints[index - 1];
      if (gap > maxPollGapMs) {
        report(
          "NO_AUTO_REFRESH",
          checkpoints[index],
          `no document refresh for ${gap}ms while the document was still in flight`,
        );
        break;
      }
    }
  }

  if (!terminal && timeline.timedOut) {
    const lastLabel = uiSamples.at(-1)?.label ?? "";
    if (classifyUiDocumentLabel(lastLabel) !== "error") {
      report(
        "INDEFINITE_SPINNER",
        timeline.deadlineMs,
        `the processing budget ended with the document still shown as "${lastLabel || "(no row)"}"`,
      );
    }
  }

  return { outcome, violations };
}
