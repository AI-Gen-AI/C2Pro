/**
 * TS-UT-PJ01-PROCESSING-001 — browser-visible processing must be honest and self-updating.
 *
 * The evaluator judges a timeline recorded WITHOUT page reloads: document-list poll
 * responses the app made on its own, and the status label the user saw.
 */
import { describe, expect, it } from "vitest";

import { evaluateProcessingTimeline, type ProcessingTimeline } from "./processing-evaluator";

function timeline(overrides: Partial<ProcessingTimeline>): ProcessingTimeline {
  return {
    startedAtMs: 0,
    deadlineMs: 240_000,
    polls: [],
    uiSamples: [],
    ...overrides,
  };
}

const codes = (result: ReturnType<typeof evaluateProcessingTimeline>) => result.violations.map((v) => v.code);

describe("evaluateProcessingTimeline", () => {
  it("accepts a clean run: polls on its own, labels follow the backend, ends analyzed", () => {
    const result = evaluateProcessingTimeline(
      timeline({
        polls: [
          { atMs: 5_000, stage: "queued" },
          { atMs: 10_000, stage: "processing" },
          { atMs: 15_000, stage: "processing" },
          { atMs: 20_000, stage: "analyzed" },
        ],
        uiSamples: [
          { atMs: 6_000, label: "Uploaded" },
          { atMs: 11_000, label: "Processing" },
          { atMs: 21_000, label: "Analyzed" },
        ],
      }),
    );
    expect(result.outcome).toBe("analyzed");
    expect(result.violations).toEqual([]);
  });

  it("flags FALSE_SUCCESS when the UI says Analyzed before analysis completed", () => {
    const result = evaluateProcessingTimeline(
      timeline({
        polls: [
          { atMs: 5_000, stage: "parsed_pending_analysis" },
          { atMs: 60_000, stage: "analyzed" },
        ],
        uiSamples: [
          { atMs: 6_000, label: "Analyzed" },
          { atMs: 61_000, label: "Analyzed" },
        ],
      }),
    );
    expect(codes(result)).toContain("FALSE_SUCCESS");
  });

  it("flags HIDDEN_ERROR when the backend failed but the UI keeps showing progress", () => {
    const result = evaluateProcessingTimeline(
      timeline({
        polls: [
          { atMs: 5_000, stage: "processing" },
          { atMs: 10_000, stage: "error" },
        ],
        uiSamples: [
          { atMs: 11_000, label: "Processing" },
          { atMs: 40_000, label: "Processing" },
        ],
      }),
    );
    expect(result.outcome).toBe("error");
    expect(codes(result)).toContain("HIDDEN_ERROR");
  });

  it("flags MANUAL_REFRESH_REQUIRED when the backend finished but the label never caught up", () => {
    const result = evaluateProcessingTimeline(
      timeline({
        polls: [{ atMs: 20_000, stage: "analyzed" }],
        uiSamples: [
          { atMs: 21_000, label: "Processing" },
          { atMs: 60_000, label: "Processing" },
        ],
      }),
    );
    expect(codes(result)).toContain("MANUAL_REFRESH_REQUIRED");
  });

  it("flags NO_AUTO_REFRESH when the app stops polling while the document is still in flight", () => {
    const result = evaluateProcessingTimeline(
      timeline({
        polls: [
          { atMs: 5_000, stage: "processing" },
          { atMs: 90_000, stage: "analyzed" },
        ],
        uiSamples: [
          { atMs: 6_000, label: "Processing" },
          { atMs: 91_000, label: "Analyzed" },
        ],
      }),
      { maxPollGapMs: 15_000 },
    );
    expect(codes(result)).toContain("NO_AUTO_REFRESH");
  });

  it("flags INDEFINITE_SPINNER when the budget ends with the user still watching progress", () => {
    const result = evaluateProcessingTimeline(
      timeline({
        deadlineMs: 30_000,
        polls: [
          { atMs: 5_000, stage: "processing" },
          { atMs: 25_000, stage: "processing" },
        ],
        uiSamples: [{ atMs: 29_000, label: "Processing" }],
        timedOut: true,
      }),
      { maxPollGapMs: 30_000 },
    );
    expect(result.outcome).toBe("timeout");
    expect(codes(result)).toContain("INDEFINITE_SPINNER");
  });

  it("flags DOCUMENT_NOT_VISIBLE when the uploaded document never appears in the list", () => {
    const result = evaluateProcessingTimeline(
      timeline({ polls: [{ atMs: 5_000, stage: "analyzed" }], uiSamples: [] }),
    );
    expect(codes(result)).toContain("DOCUMENT_NOT_VISIBLE");
  });

  it("does not punish the label for lagging inside the grace window", () => {
    const result = evaluateProcessingTimeline(
      timeline({
        polls: [
          { atMs: 5_000, stage: "processing" },
          { atMs: 10_000, stage: "analyzed" },
        ],
        uiSamples: [
          { atMs: 11_000, label: "Processing" },
          { atMs: 16_000, label: "Analyzed" },
        ],
      }),
      { labelGraceMs: 12_000 },
    );
    expect(result.violations).toEqual([]);
  });
});
